import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text

from models.base import Base
from utils.schema_sync import add_missing_columns_safe, sync_missing_columns_sync


def test_sync_missing_columns_adds_new_columns():
    metadata = MetaData()
    test_table = Table(
        "sample_table",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("title", String),
        Column("delivery_image", String, nullable=True),
        Column("is_active", Integer, default=1),
    )

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sample_table (id INTEGER PRIMARY KEY, title VARCHAR);"))

    with engine.begin() as conn:
        added = sync_missing_columns_sync(conn, metadata)

    assert "sample_table.delivery_image" in added
    assert "sample_table.is_active" in added

    inspector = inspect(engine)
    col_names = {c["name"] for c in inspector.get_columns("sample_table")}
    assert "id" in col_names
    assert "title" in col_names
    assert "delivery_image" in col_names
    assert "is_active" in col_names


def test_sync_missing_columns_is_idempotent():
    metadata = MetaData()
    Table(
        "idempotent_table",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE idempotent_table (id INTEGER PRIMARY KEY, name VARCHAR);"))

    with engine.begin() as conn:
        first_run = sync_missing_columns_sync(conn, metadata)
    assert first_run == []

    with engine.begin() as conn:
        second_run = sync_missing_columns_sync(conn, metadata)
    assert second_run == []


def test_sync_missing_columns_ignores_nonexistent_tables():
    metadata = MetaData()
    Table(
        "table_not_in_db",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
    )

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        added = sync_missing_columns_sync(conn, metadata)

    assert added == []


@pytest.mark.asyncio
async def test_add_missing_columns_safe_with_engine():
    metadata = MetaData()
    Table(
        "async_sample",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("code", String),
        Column("delivery_image", String, nullable=True),
    )

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE async_sample (id INTEGER PRIMARY KEY, code VARCHAR);"))

    added = await add_missing_columns_safe(target=engine, metadata=metadata)
    assert "async_sample.delivery_image" in added

    inspector = inspect(engine)
    col_names = {c["name"] for c in inspector.get_columns("async_sample")}
    assert "delivery_image" in col_names


@pytest.mark.asyncio
async def test_add_missing_columns_safe_handles_invalid_target():
    result = await add_missing_columns_safe(target="invalid_target")
    assert result == []


@pytest.mark.asyncio
async def test_schema_sync_with_base_models():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, price FLOAT);"))
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, telegram_id BIGINT);"))

    added = await add_missing_columns_safe(target=engine, metadata=Base.metadata)
    assert "items.delivery_image" in added
    assert "users.is_banned" in added

    inspector = inspect(engine)
    items_cols = {c["name"] for c in inspector.get_columns("items")}
    users_cols = {c["name"] for c in inspector.get_columns("users")}

    assert "delivery_image" in items_cols
    assert "is_sold" in items_cols
    assert "is_banned" in users_cols
    assert "language" in users_cols
