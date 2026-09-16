import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InputMediaPhoto, InputMediaVideo, InputMediaAnimation

from callbacks import AllCategoriesCallback, MediaManagementCallback
from enums.bot_entity import BotEntity
from enums.item_type import ItemType
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from services.category import CategoryService
from services.item import ItemService
from services.media import MediaService
from services.subcategory import SubcategoryService
from utils.utils import get_text


@pytest.mark.asyncio
@pytest.mark.parametrize("media_id,media_class", [
    ("0shared-photo", InputMediaPhoto), ("1shared-video", InputMediaVideo),
    ("2shared-animation", InputMediaAnimation),
])
@pytest.mark.parametrize("city", [ItemType.DIGITAL, ItemType.PHYSICAL])
async def test_shared_media_throughout_catalogue(monkeypatch, media_id, media_class, city):
    category = SimpleNamespace(id=1, name="Cartukai 🛒", media_id="0old-category")
    subcategory = SimpleNamespace(id=2, name="Sub", media_id="0old-subcategory")
    item = SimpleNamespace(item_type=city, category_id=1, subcategory_id=2,
                           subcategory_name="Sub", price=5, description="Description")
    button_lookup = AsyncMock(return_value=SimpleNamespace(media_id=media_id))
    monkeypatch.setattr("services.category.ButtonMediaRepository.get_by_button", button_lookup)
    monkeypatch.setattr("services.category.CategoryRepository.get", AsyncMock(return_value=[category]))
    monkeypatch.setattr("services.category.CategoryRepository.get_maximum_page", AsyncMock(return_value=0))
    monkeypatch.setattr("services.subcategory.CategoryRepository.get_by_id", AsyncMock(return_value=category))
    monkeypatch.setattr("services.subcategory.SubcategoryRepository.get_by_id", AsyncMock(return_value=subcategory))
    monkeypatch.setattr("services.subcategory.SubcategoryRepository.get_paginated_by_category_id", AsyncMock(return_value=[item]))
    monkeypatch.setattr("services.subcategory.SubcategoryRepository.get_maximum_page", AsyncMock(return_value=0))
    monkeypatch.setattr("services.subcategory.ItemRepository.get_available_qty", AsyncMock(return_value=4))
    monkeypatch.setattr("services.subcategory.ItemRepository.get_single", AsyncMock(return_value=item))
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    results = [await ItemService.get_all_types(None, None, Language.EN)]
    category_result = await CategoryService.get_buttons(
        AllCategoriesCallback.create(level=1, item_type=city), state, None, Language.EN)
    results.append(category_result)
    buttons = [button for row in category_result[1].as_markup().inline_keyboard for button in row]
    cartukai = next(button for button in buttons if button.text == "Cartukai 🛒")
    callback = AllCategoriesCallback.unpack(cartukai.callback_data)
    assert callback.item_type == city and callback.category_id == 1 and callback.level == 2
    for category_id in [1, None]:
        results.append(await SubcategoryService.get_buttons(
            AllCategoriesCallback.create(level=2, item_type=city, category_id=category_id),
            state, None, Language.EN))
    results.append(await SubcategoryService.get_select_quantity_buttons(
        AllCategoriesCallback.create(level=3, item_type=city, category_id=1, subcategory_id=2), None, Language.EN))
    for media, keyboard in results:
        assert isinstance(media, media_class)
        assert media.media == media_id[1:]
        assert media.caption
        assert keyboard.as_markup().inline_keyboard
    for call in button_lookup.await_args_list:
        assert call.args[0] == KeyboardButton.ALL_CATEGORIES


@pytest.mark.asyncio
@pytest.mark.parametrize("language", list(Language))
async def test_faq_is_text_only(language):
    # Load the handler without booting run.py's production bot and web server.
    tree = ast.parse((Path(__file__).resolve().parents[1] / "run.py").read_text())
    handler = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "faq")
    handler.decorator_list = []
    handler.returns = None
    for arg in handler.args.args:
        arg.annotation = None
    namespace = {"get_text": get_text, "BotEntity": BotEntity}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "run.py", "exec"), namespace)
    message = SimpleNamespace(answer=AsyncMock())
    await namespace["faq"](message, None, language)
    message.answer.assert_awaited_once_with(get_text(language, BotEntity.USER, "faq_string"))


@pytest.mark.asyncio
async def test_faq_media_not_offered_in_admin_menu():
    _, keyboard = await MediaService.get_menu(MediaManagementCallback.create(level=0), Language.EN)
    assert all("FAQ" not in (button.callback_data or "")
               for row in keyboard.as_markup().inline_keyboard for button in row)


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [1, 2])
@pytest.mark.parametrize("filtered", [False, True])
async def test_catalogue_search_keeps_shared_media(monkeypatch, level, filtered):
    from handlers.user.all_categories import all_categories, show_subcategories_in_category

    monkeypatch.setattr("handlers.user.all_categories.ButtonMediaRepository.get_by_button",
                        AsyncMock(return_value=SimpleNamespace(media_id="1shared-video")))
    monkeypatch.setattr("services.category.CategoryRepository.get", AsyncMock(return_value=[]))
    monkeypatch.setattr("services.category.CategoryRepository.get_maximum_page", AsyncMock(return_value=0))
    monkeypatch.setattr("services.subcategory.SubcategoryRepository.get_paginated_by_category_id",
                        AsyncMock(return_value=[]))
    monkeypatch.setattr("services.subcategory.SubcategoryRepository.get_maximum_page", AsyncMock(return_value=0))
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))
    if filtered:
        await state.update_data(filter="missing")
    callback = SimpleNamespace(message=SimpleNamespace(edit_media=AsyncMock()))
    handler = all_categories if level == 1 else show_subcategories_in_category
    await handler(callback=callback,
                  callback_data=AllCategoriesCallback.create(level=level, item_type=ItemType.DIGITAL,
                                                             is_filter_enabled=True),
                  state=state, session=None, language=Language.EN)
    sent = callback.message.edit_media.await_args.kwargs
    assert isinstance(sent["media"], InputMediaVideo)
    assert sent["media"].media == "shared-video"
    assert sent["reply_markup"].inline_keyboard
