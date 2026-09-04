"""Checkout flow: items from every city are bought and delivered the same way.

Kaunas (PHYSICAL) items no longer ask for a shipping address or a shipping
option - the buyer confirms, pays from the balance and immediately receives the
item data together with its delivery photo, exactly like Panevezys (DIGITAL).
"""
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage

from callbacks import CartCallback
from enums.buy_status import BuyStatus
from enums.item_type import ItemType
from enums.language import Language
from models.cartItem import CartItemDTO
from models.item import ItemAvailabilityDTO, ItemDTO
from services.cart import CartService
from utils.utils import get_text
from enums.bot_entity import BotEntity


def _make_state() -> FSMContext:
    storage = MemoryStorage()
    return FSMContext(storage=storage, key=StorageKey(chat_id=42, user_id=42, bot_id=1))


def _callback() -> SimpleNamespace:
    return SimpleNamespace(from_user=SimpleNamespace(id=42))


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=1, telegram_id=42, top_up_amount=1000.0, consume_records=0.0)


def _cart_item(item_type: ItemType, cart_item_id: int = 11, quantity: int = 2) -> CartItemDTO:
    return CartItemDTO(id=cart_item_id,
                       cart_id=1,
                       item_type=item_type,
                       category_id=1,
                       subcategory_id=2,
                       quantity=quantity)


def _availability(item_type: ItemType, price: float = 20.0, available_qty: int = 5) -> ItemAvailabilityDTO:
    return ItemAvailabilityDTO(item_type=item_type,
                               category_id=1,
                               subcategory_id=2,
                               price=price,
                               description="Tee",
                               available_qty=available_qty)


def _purchased_item(item_id: int, item_type: ItemType, data: str, image: str | None) -> ItemDTO:
    return ItemDTO(id=item_id,
                   item_type=item_type,
                   category_id=1,
                   subcategory_id=2,
                   price=20.0,
                   description="Tee",
                   private_data=data,
                   delivery_image=image,
                   is_sold=False)


def _patch_cart_dependencies(monkeypatch, cart_items, availability_map, purchased_items=None):
    async def _get_by_tgid(telegram_id, session):
        return _user()

    async def _get_all_by_user_id(user_id, session):
        return cart_items

    async def _get_availability(items, session):
        return availability_map

    async def _get_subcategories_by_ids(ids, session):
        return [SimpleNamespace(id=2, name="Shirt")]

    async def _get_purchased_items(item_type, category_id, subcategory_id, quantity, session):
        return [item for item in (purchased_items or [])
                if item.item_type == item_type][:quantity]

    async def _noop(*args, **kwargs):
        return None

    async def _create_buy(buy_dto, session):
        buy_dto.id = 7
        created_buys.append(buy_dto)
        return buy_dto

    async def _create_buy_item(buy_item_dto, session):
        buy_item_seq["next_id"] += 1
        buy_item_dto.id = buy_item_seq["next_id"]
        created_buy_items.append(buy_item_dto)
        return buy_item_dto

    created_buys = []
    created_buy_items = []
    buy_item_seq = {"next_id": 499}
    monkeypatch.setattr("services.cart.UserRepository.get_by_tgid", _get_by_tgid)
    monkeypatch.setattr("services.cart.UserRepository.update", _noop)
    monkeypatch.setattr("services.cart.CartItemRepository.get_all_by_user_id", _get_all_by_user_id)
    monkeypatch.setattr("services.cart.CartItemRepository.remove_from_cart", _noop)
    monkeypatch.setattr("services.cart.ItemRepository.get_availability_by_cart_items", _get_availability)
    monkeypatch.setattr("services.cart.ItemRepository.get_purchased_items", _get_purchased_items)
    monkeypatch.setattr("services.cart.ItemRepository.update", _noop)
    monkeypatch.setattr("services.cart.SubcategoryRepository.get_by_ids", _get_subcategories_by_ids)
    monkeypatch.setattr("services.cart.BuyRepository.create", _create_buy)
    monkeypatch.setattr("services.cart.BuyItemRepository.create_single", _create_buy_item)
    monkeypatch.setattr("services.cart.NotificationService.new_buy", _noop)
    return created_buys


@pytest.mark.asyncio
async def test_checkout_kaunas_item_confirms_straight_into_the_purchase(monkeypatch):
    """No shipping address and no shipping option step: confirm buys immediately."""
    cart_item = _cart_item(ItemType.PHYSICAL)
    _patch_cart_dependencies(monkeypatch,
                             [cart_item],
                             {(cart_item.item_type, 1, 2): _availability(ItemType.PHYSICAL)})

    msg, kb_builder = await CartService.checkout_processing(
        _callback(), CartCallback.create(level=2), _make_state(), session=None, language=Language.EN)

    assert "Kaunas" in msg  # the city label is shown instead of "Physical"
    assert "shipping" not in msg.lower()
    confirm_button = kb_builder.as_markup().inline_keyboard[0][0]
    confirm_data = CartCallback.unpack(confirm_button.callback_data)
    assert confirm_data.level == 6
    assert confirm_data.confirmation is True
    assert confirm_data.shipping_option_id is None


@pytest.mark.asyncio
async def test_checkout_mixed_cities_needs_no_shipping_details(monkeypatch):
    cart_items = [_cart_item(ItemType.PHYSICAL, cart_item_id=11),
                  _cart_item(ItemType.DIGITAL, cart_item_id=12)]
    availability_map = {
        (ItemType.PHYSICAL, 1, 2): _availability(ItemType.PHYSICAL),
        (ItemType.DIGITAL, 1, 2): _availability(ItemType.DIGITAL, price=10.0),
    }
    _patch_cart_dependencies(monkeypatch, cart_items, availability_map)

    msg, kb_builder = await CartService.checkout_processing(
        _callback(), CartCallback.create(level=2), _make_state(), session=None, language=Language.EN)

    assert "Kaunas" in msg and "Panevezys" in msg
    assert "$60.00" in msg  # 2 x 20.0 + 2 x 10.0, no shipping cost added
    confirm_data = CartCallback.unpack(kb_builder.as_markup().inline_keyboard[0][0].callback_data)
    assert (confirm_data.level, confirm_data.confirmation) == (6, True)


@pytest.mark.asyncio
async def test_buy_processing_kaunas_item_is_completed_and_delivered(monkeypatch):
    """A Kaunas purchase is COMPLETED right away and its data + photo are sent."""
    cart_item = _cart_item(ItemType.PHYSICAL, quantity=2)
    purchased = [
        _purchased_item(101, ItemType.PHYSICAL, "PICKUP-CODE-1", "kaunas-photo-1"),
        _purchased_item(102, ItemType.PHYSICAL, "PICKUP-CODE-2", "kaunas-photo-2"),
    ]
    created_buys = _patch_cart_dependencies(
        monkeypatch,
        [cart_item],
        {(cart_item.item_type, 1, 2): _availability(ItemType.PHYSICAL)},
        purchased_items=purchased,
    )
    delivered = []

    async def _deliver(telegram_id, items, language, **kwargs):
        delivered.append((telegram_id, items, language, kwargs))

    monkeypatch.setattr("services.cart.NotificationService.deliver_purchased_items", _deliver)

    msg, _kb = await CartService.buy_processing(
        _callback(),
        CartCallback.create(level=6, confirmation=True),
        _make_state(),
        session=None,
        language=Language.EN,
    )

    assert msg == get_text(Language.EN, BotEntity.USER, "purchase_completed")
    buy = created_buys[0]
    assert buy.status == BuyStatus.COMPLETED
    assert buy.shipping_address is None
    assert buy.shipping_option_id is None
    assert buy.total_price == 40.0
    assert all(item.is_sold for item in purchased)
    assert delivered[0][0] == 42
    assert delivered[0][3]["buy_id"] == 7
    assert [item.private_data for item in delivered[0][1]] == ["PICKUP-CODE-1", "PICKUP-CODE-2"]
    assert [item.delivery_image for item in delivered[0][1]] == ["kaunas-photo-1", "kaunas-photo-2"]


@pytest.mark.asyncio
async def test_buy_processing_delivers_both_cities_the_same_way(monkeypatch):
    cart_items = [_cart_item(ItemType.PHYSICAL, cart_item_id=11, quantity=1),
                  _cart_item(ItemType.DIGITAL, cart_item_id=12, quantity=1)]
    purchased = [
        _purchased_item(101, ItemType.PHYSICAL, "PICKUP-CODE-1", "kaunas-photo"),
        _purchased_item(201, ItemType.DIGITAL, "STEAM-KEY-1", "panevezys-photo"),
    ]
    availability_map = {
        (ItemType.PHYSICAL, 1, 2): _availability(ItemType.PHYSICAL),
        (ItemType.DIGITAL, 1, 2): _availability(ItemType.DIGITAL, price=10.0),
    }
    created_buys = _patch_cart_dependencies(monkeypatch, cart_items, availability_map, purchased)
    delivered = []

    async def _deliver(telegram_id, items, language, **kwargs):
        delivered.append((telegram_id, items, language, kwargs))

    monkeypatch.setattr("services.cart.NotificationService.deliver_purchased_items", _deliver)

    await CartService.buy_processing(
        _callback(),
        CartCallback.create(level=6, confirmation=True),
        _make_state(),
        session=None,
        language=Language.EN,
    )

    assert created_buys[0].status == BuyStatus.COMPLETED
    assert created_buys[0].total_price == 30.0
    delivered_data = {item.private_data for item in delivered[0][1]}
    assert delivered_data == {"PICKUP-CODE-1", "STEAM-KEY-1"}


@pytest.mark.asyncio
async def test_buy_processing_passes_review_map_to_delivery(monkeypatch):
    """The delivery gets a per-item buyItem map so review buttons can be attached."""
    cart_items = [_cart_item(ItemType.PHYSICAL, cart_item_id=11, quantity=1),
                  _cart_item(ItemType.DIGITAL, cart_item_id=12, quantity=1)]
    purchased = [
        _purchased_item(101, ItemType.PHYSICAL, "PICKUP-CODE-1", "kaunas-photo"),
        _purchased_item(201, ItemType.DIGITAL, "STEAM-KEY-1", "panevezys-photo"),
    ]
    availability_map = {
        (ItemType.PHYSICAL, 1, 2): _availability(ItemType.PHYSICAL),
        (ItemType.DIGITAL, 1, 2): _availability(ItemType.DIGITAL, price=10.0),
    }
    _patch_cart_dependencies(monkeypatch, cart_items, availability_map, purchased)
    delivered = []

    async def _deliver(telegram_id, items, language, **kwargs):
        delivered.append((telegram_id, items, language, kwargs))

    monkeypatch.setattr("services.cart.NotificationService.deliver_purchased_items", _deliver)

    await CartService.buy_processing(
        _callback(),
        CartCallback.create(level=6, confirmation=True),
        _make_state(),
        session=None,
        language=Language.EN,
    )

    assert len(delivered) == 1
    _telegram_id, items, _language, kwargs = delivered[0]
    assert kwargs["buy_id"] == 7
    buy_item_map = kwargs["buy_item_id_by_item"]
    assert buy_item_map == {101: 500, 201: 501}
    assert [item.id for item in items] == [101, 201]
