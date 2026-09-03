import enum
import logging
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Integer, Numeric, String, inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.schema import Column, MetaData

from models.base import Base

logger = logging.getLogger(__name__)


def _quote(connection: Connection, name: str) -> str:
    """Quote an identifier the way the target dialect expects (e.g. "buyItem")."""
    return connection.dialect.identifier_preparer.quote(name)


def _get_column_type(column: Column, dialect: Any) -> str:
    try:
        return column.type.compile(dialect=dialect)
    except Exception:
        # Some types cannot be compiled on every dialect (e.g. ARRAY on SQLite).
        # Fall back to TEXT so the sync stays additive and never blocks startup.
        return "TEXT"


def _resolve_default_literal(connection: Connection, column: Column) -> str | None:
    """
    Pick a DEFAULT literal for a NOT NULL column that is added to a table which
    may already contain rows, in this order:

    1. the column's python-side default (bool -> TRUE/FALSE, int/float -> value,
       str -> quoted),
    2. the first value the dialect persists for an Enum column,
    3. a sane per-type fallback (Boolean -> FALSE, Integer/Float/Numeric -> 0,
       String/Text -> '', DateTime -> CURRENT_TIMESTAMP).

    Returns None when no safe default can be determined.
    """
    # 1) python-side default
    if column.default is not None:
        arg = getattr(column.default, "arg", None)
        if arg is not None and not callable(arg):
            if isinstance(arg, bool):
                return "TRUE" if arg else "FALSE"
            if isinstance(arg, (int, float)):
                return str(arg)
            if isinstance(arg, enum.Enum):
                # Enum member defaults (Language.EN, ItemType.DIGITAL, ...) may
                # also be str instances: quote the string the dialect actually
                # persists (the member NAME for SQLAlchemy Enums), so the
                # default stays readable by the ORM.
                if isinstance(column.type, Enum) and column.type.enums:
                    persisted = arg.name if arg.name in column.type.enums else str(arg.value)
                    return "'" + persisted.replace("'", "''") + "'"
                return "'" + str(arg.value).replace("'", "''") + "'"
            if isinstance(arg, str):
                return "'" + arg.replace("'", "''") + "'"
    # 2) first enum value (SQLAlchemy persists enum member *names* by default,
    #    so the DB default must match column.type.enums, not member.value)
    if isinstance(column.type, Enum):
        if column.type.enums:
            return "'" + column.type.enums[0].replace("'", "''") + "'"
    # 3) fallback by column type
    if isinstance(column.type, Boolean):
        return "FALSE"
    if isinstance(column.type, Numeric):  # includes Float
        return "0"
    if isinstance(column.type, Integer):
        return "0"
    if isinstance(column.type, String):  # includes Text (Enum handled above)
        return "''"
    if isinstance(column.type, DateTime):
        return "CURRENT_TIMESTAMP"
    return None


def _sync_enum_values(sync_connection: Connection, column: Column) -> list[str]:
    """
    PostgreSQL-only: make sure an existing enum TYPE knows every value the model
    declares. A database created by an older code version has a 'cryptocurrency'
    enum that predates some coins, which made inserts fail with
    "invalid input value for enum" (e.g. deposits stuck with 500s).
    Returns the list of applied ALTER TYPE statements.
    """
    if sync_connection.dialect.name != "postgresql":
        return []
    type_name = getattr(column.type, "name", None)
    if not type_name:
        return []
    existing_rows = sync_connection.execute(
        text("SELECT e.enumlabel FROM pg_enum e "
             "JOIN pg_type t ON e.enumtypid = t.oid "
             "WHERE t.typname = :type_name"),
        {"type_name": type_name},
    ).fetchall()
    existing_values = {row[0] for row in existing_rows}
    applied: list[str] = []
    for value in column.type.enums:
        if value in existing_values:
            continue
        ddl = f'ALTER TYPE "{type_name}" ADD VALUE IF NOT EXISTS \'{value}\''
        sync_connection.execute(text(ddl))
        applied.append(ddl)
        logger.warning("Schema sync applied: %s", ddl)
    return applied


def add_missing_columns(sync_connection: Connection, metadata: MetaData | None = None) -> list[str]:
    """
    Additive-only schema sync: for every ORM table that already exists in the
    database, add every model column that is missing (primary keys are skipped,
    they can never go missing on an existing table).

    PostgreSQL uses ``ADD COLUMN IF NOT EXISTS``; other dialects use a plain
    ``ADD COLUMN`` (existence is checked via the inspector first). For
    PostgreSQL Enum columns the enum type is created first (``checkfirst``)
    and missing enum VALUES are healed on already-existing enum columns
    (older databases predate newer cryptocurrencies). Nothing is ever dropped,
    renamed or type-altered. Returns the list of "table.column" entries that
    were added (plus the applied enum ALTER statements).
    """
    if metadata is None:
        metadata = Base.metadata

    inspector = inspect(sync_connection)
    existing_tables = set(inspector.get_table_names())
    is_postgresql = sync_connection.dialect.name == "postgresql"
    add_clause = "ADD COLUMN IF NOT EXISTS" if is_postgresql else "ADD COLUMN"
    added_columns: list[str] = []

    for table_name, table in metadata.tables.items():
        if table_name not in existing_tables:
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
        quoted_table = _quote(sync_connection, table_name)
        for column in table.columns:
            if column.name in existing_cols:
                # The column itself already exists: nothing to add, but keep its
                # PostgreSQL enum TYPE values current (additive-only).
                if is_postgresql and isinstance(column.type, Enum):
                    added_columns.extend(_sync_enum_values(sync_connection, column))
                continue
            if column.primary_key:
                continue
            try:
                if is_postgresql and isinstance(column.type, Enum):
                    # The enum type must exist before a column can reference it.
                    column.type.create(bind=sync_connection, checkfirst=True)
                    # checkfirst=True skips creation when the type already exists
                    # (possibly with outdated values), so sync its values too.
                    added_columns.extend(_sync_enum_values(sync_connection, column))
                column_type = _get_column_type(column, sync_connection.dialect)
                not_null_sql = ""
                default_sql = ""
                if not column.nullable:
                    default_literal = _resolve_default_literal(sync_connection, column)
                    if default_literal is None:
                        # No safe default (e.g. ARRAY columns): add the column as
                        # nullable rather than break on populated tables.
                        logger.warning(
                            "Schema sync: no safe default for NOT NULL column %s.%s, "
                            "adding it as nullable", table_name, column.name)
                    else:
                        not_null_sql = " NOT NULL"
                        default_sql = f" DEFAULT {default_literal}"
                ddl = (f"ALTER TABLE {quoted_table} {add_clause} "
                       f"{_quote(sync_connection, column.name)} {column_type}"
                       f"{not_null_sql}{default_sql}")
                sync_connection.execute(text(ddl))
                added_columns.append(f"{table_name}.{column.name}")
                logger.warning("Schema sync applied: %s", ddl)
            except Exception as e:
                logger.warning(
                    "Failed to add missing column '%s' to table '%s': %s",
                    column.name,
                    table_name,
                    e,
                )

    return added_columns


def sync_missing_columns_sync(conn: Connection, metadata: MetaData | None = None) -> list[str]:
    """Backwards-compatible alias for :func:`add_missing_columns`."""
    return add_missing_columns(conn, metadata)


async def add_missing_columns_safe(
    target: Any = None,
    metadata: MetaData | None = None,
) -> list[str]:
    if target is None:
        import db
        target = db.engine

    try:
        if isinstance(target, AsyncEngine):
            async with target.begin() as conn:
                return await conn.run_sync(add_missing_columns, metadata)
        elif isinstance(target, AsyncConnection):
            return await target.run_sync(add_missing_columns, metadata)
        elif isinstance(target, AsyncSession):
            conn = await target.connection()
            return await conn.run_sync(add_missing_columns, metadata)
        elif isinstance(target, Engine):
            with target.begin() as conn:
                return add_missing_columns(conn, metadata)
        elif isinstance(target, (Connection, Session)):
            if isinstance(target, Session):
                return add_missing_columns(target.connection(), metadata)
            return add_missing_columns(target, metadata)
        elif hasattr(target, "begin") and callable(target.begin):
            async with target.begin() as conn:
                if hasattr(conn, "run_sync"):
                    return await conn.run_sync(add_missing_columns, metadata)
                return add_missing_columns(conn, metadata)
        else:
            logger.warning("Unsupported target type for add_missing_columns_safe: %s", type(target))
            return []
    except Exception as e:
        logger.warning("add_missing_columns_safe encountered an error: %s", e)
        return []
