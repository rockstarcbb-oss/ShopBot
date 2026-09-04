"""Purchase details: a Kaunas purchase shows its data and photo like a Panevezys one."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from aiogram.types import InputMediaPhoto

from callbacks import MyProfileCallback
from enums.buy_status import BuyStatus
from enums.item_type import ItemType
from enums.language import Language
from enums.user_role import UserRole
from models.item import ItemDTO
from services.buy import BuyService


def _buy(status=BuyStatus.COMPLETED, shipping_address=None):
    return SimpleNamespace(id=7,
                           status=status,
                           shipping_address=shipping_address,
                           shipping_option_id=None,
                           track_number=None,
                           buy_datetime=datetime(2026, 9, 4, 10, 30, tzinfo=timezone.utc))


def _patch_buy_dependencies(monkeypatch, buy, items):
    async def _get_buy_by_id(buy_id, session):
        return buy

    async def _get_buy_item_by_id(buy_item_id, session):
        return SimpleNamespace(id=3, item_ids=[item.id for item in items])

    async def _get_items_by_id_list(item_ids, session):
        return items

    async def _get_category_by_id(category_id, session):
        return SimpleNamespace(id=1, name="Merch")

    async def _get_subcategory_by_id(subcategory_id, session):
        return SimpleNamespace(id=2, name="Shirt")

    async def _get_review(buy_item_id, session):
        return None

    monkeypatch.setattr("services.buy.BuyRepository.get_by_id", _get_buy_by_id)
    monkeypatch.setattr("services.buy.BuyItemRepository.get_by_id", _get_buy_item_by_id)
    monkeypatch.setattr("services.buy.ItemRepository.get_by_id_list", _get_items_by_id_list)
    monkeypatch.setattr("services.buy.CategoryRepository.get_by_id", _get_category_by_id)
    monkeypatch.setattr("services.buy.SubcategoryRepository.get_by_id", _get_subcategory_by_id)
    monkeypatch.setattr("services.buy.ReviewRepository.get_by_buy_item_id", _get_review)


def _kaunas_items():
    return [
        ItemDTO(id=101,
                item_type=ItemType.PHYSICAL,
                category_id=1,
                subcategory_id=2,
                price=20.0,
                description="Tee",
                private_data="PICKUP-CODE-1",
                delivery_image="kaunas-photo-1"),
        ItemDTO(id=102,
                item_type=ItemType.PHYSICAL,
                category_id=1,
                subcategory_id=2,
                price=20.0,
                description="Tee",
                private_data="PICKUP-CODE-2",
                delivery_image=None),
    ]


@pytest.mark.asyncio
async def test_purchase_details_show_data_and_photo_for_kaunas_items(monkeypatch):
    items = _kaunas_items()
    _patch_buy_dependencies(monkeypatch, _buy(), items)

    callback_data = MyProfileCallback.create(level=5, buy_id=7, buyItem_id=3, user_role=UserRole.USER)
    media, kb_builder = await BuyService.get_purchase(callback_data, session=None, language=Language.EN)

    assert isinstance(media, InputMediaPhoto)
    assert media.media == "kaunas-photo-1"
    assert "Items:" in media.caption
    assert "PICKUP-CODE-1" in media.caption
    assert "PICKUP-CODE-2" in media.caption


@pytest.mark.asyncio
async def test_purchase_details_offer_review_for_completed_kaunas_purchase(monkeypatch):
    items = _kaunas_items()
    _patch_buy_dependencies(monkeypatch, _buy(status=BuyStatus.COMPLETED), items)

    callback_data = MyProfileCallback.create(level=5, buy_id=7, buyItem_id=3, user_role=UserRole.USER)
    _media, kb_builder = await BuyService.get_purchase(callback_data, session=None, language=Language.EN)

    buttons = [button.text for row in kb_builder.as_markup().inline_keyboard for button in row]
    assert any("Review" in text for text in buttons)


@pytest.mark.asyncio
async def test_purchase_details_without_photo_still_show_data(monkeypatch):
    items = _kaunas_items()
    for item in items:
        item.delivery_image = None
    _patch_buy_dependencies(monkeypatch, _buy(), items)

    callback_data = MyProfileCallback.create(level=5, buy_id=7, buyItem_id=3, user_role=UserRole.USER)
    result, _kb_builder = await BuyService.get_purchase(callback_data, session=None, language=Language.EN)

    assert isinstance(result, str)
    assert "PICKUP-CODE-1" in result
    assert "PICKUP-CODE-2" in result
