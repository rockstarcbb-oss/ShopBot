from contextlib import asynccontextmanager
import importlib
import pkgutil

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import models
from enums.item_type import ItemType
from enums.sort_order import SortOrder
from enums.sort_property import SortProperty
from models.category import Category
from models.item import Item
from models.subcategory import Subcategory
from repositories.category import CategoryRepository


@pytest.fixture
def catalogue(monkeypatch):
    # Register all relationship targets, but create only the catalogue tables.
    for module in pkgutil.iter_modules(models.__path__):
        importlib.import_module(f"models.{module.name}")
    engine = create_engine("sqlite://")
    Category.__table__.create(engine)
    Subcategory.__table__.create(engine)
    Item.__table__.create(engine)
    with Session(engine) as session:
        async def execute(stmt, session):
            return session.execute(stmt)

        async def commit(session):
            session.commit()

        @asynccontextmanager
        async def get_session():
            yield session

        monkeypatch.setattr("repositories.category.session_execute", execute)
        monkeypatch.setattr("repositories.category.session_commit", commit)
        monkeypatch.setattr("repositories.category.get_db_session", get_session)
        monkeypatch.setattr("repositories.category.get_bot_photo_id", lambda: "fallback")
        yield session
    engine.dispose()


@pytest.mark.asyncio
async def test_startup_seeds_once_and_preserves_existing_category(catalogue):
    await CategoryRepository.init_permanent_categories()
    category = catalogue.scalar(select(Category))
    category.media_id = "1custom-video"
    original_id = category.id
    catalogue.commit()
    await CategoryRepository.init_permanent_categories()
    categories = catalogue.scalars(select(Category)).all()
    assert [(c.id, c.name, c.media_id) for c in categories] == [
        (original_id, "Cartukai 🛒", "1custom-video")
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("city", [ItemType.DIGITAL, ItemType.PHYSICAL, None])
async def test_permanent_category_is_visible_without_stock(catalogue, city):
    await CategoryRepository.init_permanent_categories()
    catalogue.add(Category(name="Empty ordinary category", media_id="0photo"))
    catalogue.commit()
    categories = await CategoryRepository.get({}, None, city, 0, catalogue)
    assert [c.name for c in categories] == ["Cartukai 🛒"]
    assert await CategoryRepository.get_maximum_page(None, catalogue, city) == 0
    assert await CategoryRepository.get({}, ["missing"], city, 0, catalogue) == []
    assert len(await CategoryRepository.get({}, ["cartukai"], city, 0, catalogue)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("city", [ItemType.DIGITAL, ItemType.PHYSICAL])
async def test_sold_stock_city_filter_and_pagination(catalogue, monkeypatch, city):
    monkeypatch.setattr("config.PAGE_ENTRIES", 2)
    await CategoryRepository.init_permanent_categories()
    permanent = catalogue.scalar(select(Category))
    other_city = ItemType.PHYSICAL if city == ItemType.DIGITAL else ItemType.DIGITAL
    subcategory = Subcategory(name="Sub", media_id="0photo")
    ordinary = [Category(name=name, media_id="0photo") for name in ["A", "B", "Other", "Sold"]]
    catalogue.add_all([subcategory, *ordinary])
    catalogue.flush()
    for category, item_city, sold in [
        (permanent, city, True), (permanent, other_city, False),
        (ordinary[0], city, False), (ordinary[0], city, False),
        (ordinary[1], city, False), (ordinary[2], other_city, False),
        (ordinary[3], city, True),
    ]:
        catalogue.add(Item(category_id=category.id, subcategory_id=subcategory.id,
                           item_type=item_city, price=1, description="", is_sold=sold))
    catalogue.commit()
    sorting = {str(SortProperty.NAME.value): SortOrder.ASC.value}
    first = await CategoryRepository.get(sorting, None, city, 0, catalogue)
    second = await CategoryRepository.get(sorting, None, city, 1, catalogue)
    assert [c.name for c in first + second] == ["A", "B", "Cartukai 🛒"]
    assert await CategoryRepository.get_maximum_page(None, catalogue, city) == 1
    assert await CategoryRepository.get_maximum_page(["Cartukai"], catalogue, city) == 0
