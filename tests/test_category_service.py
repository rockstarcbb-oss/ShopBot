from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from callbacks import AllCategoriesCallback
from enums.item_type import ItemType
from enums.language import Language
from services.category import CategoryService


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    return FSMContext(storage=storage, key=StorageKey(chat_id=42, user_id=42, bot_id=1))


def _patch_empty_city_dependencies(monkeypatch):
    async def _get_empty_categories(sort_pairs, filters, item_type, page, session):
        return []

    async def _get_max_page(filters, session):
        return 0

    async def _get_button(button, session):
        return SimpleNamespace(media_id="0photo-id")

    monkeypatch.setattr("services.category.CategoryRepository.get", _get_empty_categories)
    monkeypatch.setattr("services.category.CategoryRepository.get_maximum_page", _get_max_page)
    monkeypatch.setattr("services.category.ButtonMediaRepository.get_by_button", _get_button)


@pytest.mark.asyncio
async def test_empty_city_shows_no_items_message(monkeypatch):
    """Pressing a city with no stock shows the city-specific empty message."""
    _patch_empty_city_dependencies(monkeypatch)
    callback_data = AllCategoriesCallback.create(level=1, item_type=ItemType.PHYSICAL)

    media, _kb = await CategoryService.get_buttons(callback_data, _make_state(), session=None, language=Language.EN)

    assert "Kaunas" in media.caption
    assert "No items available" in media.caption


@pytest.mark.asyncio
async def test_empty_search_results_keep_no_categories_message(monkeypatch):
    """Search results that match nothing keep the generic "no categories" text."""
    _patch_empty_city_dependencies(monkeypatch)
    callback_data = AllCategoriesCallback.create(level=1,
                                                 item_type=ItemType.DIGITAL,
                                                 is_filter_enabled=True)

    media, _kb = await CategoryService.get_buttons(callback_data, _make_state(), session=None, language=Language.EN)

    assert "No items available" not in media.caption
    assert "No categories" in media.caption
