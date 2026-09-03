import logging
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.schema import Column, MetaData

from models.base import Base

logger = logging.getLogger(__name__)


def _get_column_type(column: Column, dialect: Any) -> str:
    try:
        return column.type.compile(dialect=dialect)
    except Exception:
        if hasattr(column.type, "item_type"):
            return "TEXT"
        return "TEXT"


def _get_column_default_sql(column: Column) -> str:
    if column.server_default is not None and hasattr(column.server_default, "arg"):
        arg = column.server_default.arg
        if hasattr(arg, "text"):
            return f" DEFAULT {arg.text}"
        return f" DEFAULT {arg}"
    if column.default is not None and hasattr(column.default, "arg"):
        arg = column.default.arg
        if not callable(arg):
            if isinstance(arg, bool):
                return f" DEFAULT {'TRUE' if arg else 'FALSE'}"
            if isinstance(arg, (int, float)):
                return f" DEFAULT {arg}"
            if isinstance(arg, str):
                return f" DEFAULT '{arg}'"
            if hasattr(arg, "value"):
                return f" DEFAULT '{arg.value}'"
            if hasattr(arg, "name"):
                return f" DEFAULT '{arg.name}'"
    return ""


def sync_missing_columns_sync(conn: Connection, metadata: MetaData | None = None) -> list[str]:
    if metadata is None:
        metadata = Base.metadata

    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())
    added_columns: list[str] = []

    for table_name, table in metadata.tables.items():
        if table_name not in existing_tables:
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in existing_cols:
                col_type = _get_column_type(column, conn.dialect)
                default_clause = _get_column_default_sql(column)
                alter_stmt = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}{default_clause}"
                try:
                    conn.execute(text(alter_stmt))
                    added_columns.append(f"{table_name}.{column.name}")
                    logger.info("Added missing column '%s' to table '%s'", column.name, table_name)
                except Exception as e:
                    logger.warning(
                        "Failed to add missing column '%s' to table '%s': %s",
                        column.name,
                        table_name,
                        e,
                    )

    return added_columns


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
                return await conn.run_sync(sync_missing_columns_sync, metadata)
        elif isinstance(target, AsyncConnection):
            return await target.run_sync(sync_missing_columns_sync, metadata)
        elif isinstance(target, AsyncSession):
            conn = await target.connection()
            return await conn.run_sync(sync_missing_columns_sync, metadata)
        elif isinstance(target, Engine):
            with target.begin() as conn:
                return sync_missing_columns_sync(conn, metadata)
        elif isinstance(target, (Connection, Session)):
            if isinstance(target, Session):
                return sync_missing_columns_sync(target.connection(), metadata)
            return sync_missing_columns_sync(target, metadata)
        elif hasattr(target, "begin") and callable(target.begin):
            async with target.begin() as conn:
                if hasattr(conn, "run_sync"):
                    return await conn.run_sync(sync_missing_columns_sync, metadata)
                return sync_missing_columns_sync(conn, metadata)
        else:
            logger.warning("Unsupported target type for add_missing_columns_safe: %s", type(target))
            return []
    except Exception as e:
        logger.warning("add_missing_columns_safe encountered an error: %s", e)
        return []
