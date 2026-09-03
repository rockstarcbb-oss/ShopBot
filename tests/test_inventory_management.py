from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from enums.language import Language
from handlers.admin.constants import InventoryManagementStates
from services.inventory_management import InventoryManagementService
from utils.utils import get_bot_photo_id, NO_IMAGE_URL


class _FakeBot:
    async def edit_message_reply_markup(self, *args, **kwargs):
        return None


class _FakeMessage:
    def __init__(self, text, photo=None):
        self.html_text = text
        self.text = text
        self.bot = _FakeBot()
        self.chat = SimpleNamespace(id=1)
        self.photo = photo


async def _build_price_state(state: FSMContext):
    await state.set_state(InventoryManagementStates.price)
    await state.set_data({
        "add_type": "menu",
        "item_type": "DIGITAL",
        "category_name": "Accounts",
        "subcategory_name": "Streaming",
        "description": "1 month premium",
        "private_data": "acc1@mail.com:pass1\nacc2@mail.com:pass2",
        "chat_id": 1,
        "msg_id": 1,
    })


@pytest.mark.asyncio
async def test_get_bot_photo_id_falls_back_when_cache_file_missing(monkeypatch, tmp_path):
    """Regression: a missing static/no_image.jpeg used to raise FileNotFoundError,
    which made the add-item flow reject every price with a re-prompt loop."""
    monkeypatch.chdir(tmp_path)  # no static/ directory here
    photo = get_bot_photo_id()
    assert photo == NO_IMAGE_URL


@pytest.mark.asyncio
async def test_price_step_creates_items_when_bot_photo_cache_missing(monkeypatch, tmp_path):
    added_items = []
    created_categories = []
    created_subcategories = []

    async def _fake_category_get_or_create(name, session):
        created_categories.append(name)
        return SimpleNamespace(id=1, name=name)

    async def _fake_subcategory_get_or_create(name, session):
        created_subcategories.append(name)
        return SimpleNamespace(id=2, name=name)

    async def _fake_add_many(items, session):
        added_items.extend(items)

    async def _fake_edit_reply_markup(*args, **kwargs):
        return None

    monkeypatch.chdir(tmp_path)  # static/no_image.jpeg does not exist
    monkeypatch.setattr("services.inventory_management.CategoryRepository.get_or_create",
                        _fake_category_get_or_create)
    monkeypatch.setattr("services.inventory_management.SubcategoryRepository.get_or_create",
                        _fake_subcategory_get_or_create)
    monkeypatch.setattr("services.inventory_management.ItemRepository.add_many", _fake_add_many)
    monkeypatch.setattr("services.inventory_management.NotificationService.edit_reply_markup",
                        _fake_edit_reply_markup)

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(chat_id=1, user_id=1, bot_id=1))
    await _build_price_state(state)

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("50.0"), state, session=None, language=Language.EN)

    assert created_categories == ["Accounts"]
    assert created_subcategories == ["Streaming"]
    assert len(added_items) == 2
    assert added_items[0].price == 50.0
    assert await state.get_state() is None  # flow finished, state cleared
    assert "Please send price" not in msg


@pytest.mark.asyncio
async def test_price_step_reprompts_on_invalid_price():
    async def _fake_edit_reply_markup(*args, **kwargs):
        return None

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(chat_id=1, user_id=1, bot_id=1))
    await _build_price_state(state)

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("not a number"), state, session=None, language=Language.EN)

    assert "Please send price" in msg
    assert await state.get_state() == InventoryManagementStates.price  # still waiting for a valid price


def _fake_add_item_dependencies(monkeypatch, added_items):
    async def _fake_category_get_or_create(name, session):
        return SimpleNamespace(id=1, name=name)

    async def _fake_subcategory_get_or_create(name, session):
        return SimpleNamespace(id=2, name=name)

    async def _fake_add_many(items, session):
        added_items.extend(items)

    async def _fake_edit_reply_markup(*args, **kwargs):
        return None

    monkeypatch.setattr("services.inventory_management.CategoryRepository.get_or_create",
                        _fake_category_get_or_create)
    monkeypatch.setattr("services.inventory_management.SubcategoryRepository.get_or_create",
                        _fake_subcategory_get_or_create)
    monkeypatch.setattr("services.inventory_management.ItemRepository.add_many", _fake_add_many)
    monkeypatch.setattr("services.inventory_management.NotificationService.edit_reply_markup",
                        _fake_edit_reply_markup)


async def _build_private_data_state(state: FSMContext, item_type: str = "digital"):
    await state.set_state(InventoryManagementStates.private_data)
    await state.set_data({
        "add_type": "menu",
        "item_type": item_type,
        "category_name": "steam",
        "subcategory_name": "teamfortress",
        "description": "whatever",
        "chat_id": 1,
        "msg_id": 1,
    })


@pytest.mark.asyncio
async def test_delivery_image_per_code_line(monkeypatch):
    """Each line of activation codes can get its own delivery photo (or none)."""
    added_items = []
    _fake_add_item_dependencies(monkeypatch, added_items)

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(chat_id=1, user_id=1, bot_id=1))
    await _build_private_data_state(state)

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("CODE-AAAA\nCODE-BBBB\nCODE-CCCC"), state, session=None, language=Language.EN)
    assert await state.get_state() == InventoryManagementStates.delivery_image
    assert "1 of 3" in msg and "CODE-AAAA" in msg  # photo prompt for the first code line

    # photo for line 1 (Telegram sends several sizes, the last one is the biggest)
    photo_message = _FakeMessage(None, photo=[SimpleNamespace(file_id="photo-1-small"),
                                              SimpleNamespace(file_id="photo-1")])
    msg, _kb = await InventoryManagementService.add_item_menu(
        photo_message, state, session=None, language=Language.EN)
    assert "2 of 3" in msg and "CODE-BBBB" in msg

    # invalid input re-prompts for the same line
    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("hello"), state, session=None, language=Language.EN)
    assert "2 of 3" in msg

    # skip line 2
    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("skip"), state, session=None, language=Language.EN)
    assert "3 of 3" in msg and "CODE-CCCC" in msg

    # image URL for line 3, then the price step
    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("https://example.com/card.png"), state, session=None, language=Language.EN)
    assert await state.get_state() == InventoryManagementStates.price
    assert "Please send price" in msg

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("10.0"), state, session=None, language=Language.EN)
    assert len(added_items) == 3
    assert added_items[0].private_data == "CODE-AAAA"
    assert added_items[0].delivery_image == "photo-1"
    assert added_items[1].private_data == "CODE-BBBB"
    assert added_items[1].delivery_image is None
    assert added_items[2].private_data == "CODE-CCCC"
    assert added_items[2].delivery_image == "https://example.com/card.png"
    assert await state.get_state() is None  # flow finished


@pytest.mark.asyncio
async def test_blank_private_data_reprompts():
    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(chat_id=1, user_id=1, bot_id=1))
    await _build_private_data_state(state)

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("  \n\n  "), state, session=None, language=Language.EN)

    assert await state.get_state() == InventoryManagementStates.private_data
    assert "data that the user will receive" in msg


@pytest.mark.asyncio
async def test_delivery_image_single_line_keeps_original_prompt(monkeypatch):
    added_items = []
    _fake_add_item_dependencies(monkeypatch, added_items)

    storage = MemoryStorage()
    state = FSMContext(storage=storage, key=StorageKey(chat_id=1, user_id=1, bot_id=1))
    await _build_private_data_state(state)

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("CODE-AAAA"), state, session=None, language=Language.EN)
    assert "of 1" not in msg  # single line: classic single-image prompt

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("skip"), state, session=None, language=Language.EN)
    assert await state.get_state() == InventoryManagementStates.price

    msg, _kb = await InventoryManagementService.add_item_menu(
        _FakeMessage("5.0"), state, session=None, language=Language.EN)
    assert len(added_items) == 1
    assert added_items[0].private_data == "CODE-AAAA"
    assert added_items[0].delivery_image is None
