import logging

import pytest
import sqlalchemy
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

# sqlite has no ARRAY type: alias it to JSON so that ORM models using
# ARRAY columns (buyItem.item_ids) can be imported/inspected on sqlite.
sqlalchemy.ARRAY = sqlalchemy.JSON

from enums.item_type import ItemType
from enums.language import Language
from models.base import Base
from models.item import Item
from models.user import User

# Import every model so Base.metadata and the mapper registry are complete
# regardless of which other test modules were collected before this one.
import models.button_media  # noqa: F401
import models.buy  # noqa: F401
import models.buyItem  # noqa: F401
import models.cart  # noqa: F401
import models.cartItem  # noqa: F401
import models.category  # noqa: F401
import models.coupon  # noqa: F401
import models.deposit  # noqa: F401
import models.payment  # noqa: F401
import models.referral  # noqa: F401
import models.review  # noqa: F401
import models.shipping_option  # noqa: F401
import models.subcategory  # noqa: F401

from utils.schema_sync import add_missing_columns, add_missing_columns_safe, sync_missing_columns_sync


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


@pytest.mark.asyncio
async def test_add_missing_columns_heals_items_without_delivery_image(caplog):
    """An 'old' items table without delivery_image gets the column back-filled
    and the ORM can insert items again afterwards."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                item_type VARCHAR(10) NOT NULL,
                category_id INTEGER NOT NULL,
                subcategory_id INTEGER NOT NULL,
                private_data VARCHAR,
                price FLOAT NOT NULL,
                is_sold BOOLEAN NOT NULL,
                is_new BOOLEAN NOT NULL,
                description VARCHAR NOT NULL
            )
        """))

    with caplog.at_level(logging.WARNING, logger="utils.schema_sync"):
        with engine.begin() as conn:
            added = add_missing_columns(conn, Base.metadata)

    assert "items.delivery_image" in added
    inspector = inspect(engine)
    assert "delivery_image" in {c["name"] for c in inspector.get_columns("items")}
    assert any("Schema sync applied" in record.message for record in caplog.records)

    # the ORM can insert items again
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.add(Item(item_type=ItemType.DIGITAL,
                         category_id=1,
                         subcategory_id=1,
                         price=5.0,
                         description="1 month of premium",
                         private_data="CODE-0001",
                         delivery_image="photo-0001"))
        session.commit()
        stored = session.query(Item).one()
        assert stored.private_data == "CODE-0001"
        assert stored.delivery_image == "photo-0001"
        assert stored.is_sold is False


def test_add_missing_columns_is_idempotent_on_real_models():
    """A second sync run must not apply anything."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE items (
                id INTEGER PRIMARY KEY,
                item_type VARCHAR(10) NOT NULL,
                category_id INTEGER NOT NULL,
                subcategory_id INTEGER NOT NULL,
                private_data VARCHAR,
                price FLOAT NOT NULL,
                is_sold BOOLEAN NOT NULL,
                is_new BOOLEAN NOT NULL,
                description VARCHAR NOT NULL
            )
        """))

    with engine.begin() as conn:
        first_run = add_missing_columns(conn, Base.metadata)
    assert first_run != []

    with engine.begin() as conn:
        second_run = add_missing_columns(conn, Base.metadata)
    assert second_run == []


def test_add_missing_columns_users_referral_columns_with_defaults():
    """A 'old' users table gets language/is_banned/referral columns with working
    defaults and the ORM can insert users afterwards."""
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                telegram_username VARCHAR,
                telegram_id BIGINT NOT NULL,
                top_up_amount FLOAT,
                consume_records FLOAT,
                registered_at TIMESTAMP,
                can_receive_messages BOOLEAN
            )
        """))

    with engine.begin() as conn:
        added = add_missing_columns(conn, Base.metadata)

    assert {"users.language",
            "users.is_banned",
            "users.referral_code",
            "users.referred_by_user_id",
            "users.referred_at"} <= set(added)

    # database-level default works for the NOT NULL language column
    # (is_banned is nullable in the model, so no DB default is required:
    # the ORM supplies False client-side)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (telegram_id) VALUES (555)"))
        row = conn.execute(text(
            "SELECT language FROM users WHERE telegram_id = 555")).one()
    assert row.language == Language.EN.name  # SQLAlchemy persists enum member names

    # the ORM can insert users again
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        session.add(User(telegram_id=777))
        session.commit()
        stored = session.query(User).filter(User.telegram_id == 777).one()
        assert stored.language == Language.EN
        assert stored.is_banned is False
        assert stored.referral_code is None
        assert stored.referred_by_user_id is None
