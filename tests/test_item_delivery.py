from types import SimpleNamespace

import pytest

from enums.item_type import ItemType
from enums.language import Language
from models.item import ItemDTO
from services.item import ItemService
from services.message import MessageService
from services.notification import NotificationService


def _item(private_data: str | None,
          delivery_image: str | None = None,
          item_type: ItemType = ItemType.DIGITAL) -> ItemDTO:
    return ItemDTO(
        item_type=item_type,
        private_data=private_data,
        delivery_image=delivery_image,
    )


def _kaunas_item(private_data: str | None, delivery_image: str | None = None) -> ItemDTO:
    """An item from Kaunas (PHYSICAL) is delivered exactly like a Panevezys one."""
    return _item(private_data, delivery_image, ItemType.PHYSICAL)


def test_resolve_delivery_content_uses_stored_image():
    image, code = MessageService.resolve_delivery_content(
        _item("GAME-CODE-123", "https://cdn.example.com/qr.png")
    )
    assert image == "https://cdn.example.com/qr.png"
    assert code == "GAME-CODE-123"


def test_resolve_delivery_content_extracts_image_url_from_private_data():
    image, code = MessageService.resolve_delivery_content(
        _item("https://cdn.example.com/qr.jpg GAME-CODE-123")
    )
    assert image == "https://cdn.example.com/qr.jpg"
    assert code == "GAME-CODE-123"


def test_resolve_delivery_content_keeps_plain_code():
    image, code = MessageService.resolve_delivery_content(_item("XXXX-YYYY"))
    assert image is None
    assert code == "XXXX-YYYY"


def test_resolve_delivery_content_works_for_kaunas_items():
    image, code = MessageService.resolve_delivery_content(
        _kaunas_item("PICKUP-CODE-1", "https://cdn.example.com/parcel.png")
    )
    assert image == "https://cdn.example.com/parcel.png"
    assert code == "PICKUP-CODE-1"


def test_build_delivery_messages_groups_same_image():
    items = [
        _item("CODE-1", "file-id-1"),
        _item("CODE-2", "file-id-1"),
        _item("CODE-3"),
    ]
    deliveries = MessageService.build_delivery_messages(items, Language.EN)
    assert len(deliveries) == 2
    assert deliveries[0][0] == "file-id-1"
    assert "CODE-1" in deliveries[0][1]
    assert "CODE-2" in deliveries[0][1]
    assert deliveries[1][0] is None
    assert "CODE-3" in deliveries[1][1]


def test_build_delivery_messages_delivers_kaunas_items():
    """Kaunas items are no longer skipped: buyer gets their data and photo."""
    deliveries = MessageService.build_delivery_messages(
        [_kaunas_item("KAUNAS-DATA-1", "kaunas-photo")],
        Language.EN,
    )
    assert deliveries == [("kaunas-photo", deliveries[0][1])]
    assert "KAUNAS-DATA-1" in deliveries[0][1]


def test_build_delivery_messages_groups_items_from_both_cities():
    items = [
        _item("PANEVEZYS-DATA-1", "shared-photo"),
        _kaunas_item("KAUNAS-DATA-1", "shared-photo"),
        _kaunas_item("KAUNAS-DATA-2"),
    ]
    deliveries = MessageService.build_delivery_messages(items, Language.EN)
    assert len(deliveries) == 2
    assert deliveries[0][0] == "shared-photo"
    assert "PANEVEZYS-DATA-1" in deliveries[0][1]
    assert "KAUNAS-DATA-1" in deliveries[0][1]
    assert deliveries[1][0] is None
    assert "KAUNAS-DATA-2" in deliveries[1][1]


def test_create_message_with_bought_items_includes_kaunas_data():
    message = MessageService.create_message_with_bought_items(
        [_item("CODE-1"), _kaunas_item("KAUNAS-DATA-1")],
        Language.EN,
    )
    assert "CODE-1" in message
    assert "KAUNAS-DATA-1" in message


def test_skip_delivery_image_values():
    assert MessageService.is_skip_delivery_image("skip")
    assert MessageService.is_skip_delivery_image("NONE")
    assert MessageService.is_skip_delivery_image("-")
    assert not MessageService.is_skip_delivery_image("https://example.com/qr.png")


@pytest.mark.asyncio
async def test_parse_items_json_reads_delivery_image(tmp_path, monkeypatch):
    json_file = tmp_path / "items.json"
    json_file.write_text(
        """
        [
          {
            "item_type": "Digital",
            "category": "Games",
            "subcategory": "Steam",
            "price": 10,
            "description": "Key",
            "private_data": "AAAA-BBBB",
            "delivery_image": "https://example.com/qr.png"
          },
          {
            "item_type": "Physical",
            "category": "Merch",
            "subcategory": "Shirt",
            "price": 20,
            "description": "Tee",
            "private_data": "PICKUP-CODE-1",
            "delivery_image": "https://example.com/parcel.png"
          }
        ]
        """,
        encoding="utf-8",
    )

    async def _get_or_create(name, session):
        return SimpleNamespace(id=1 if name in {"Games", "Steam"} else 2, name=name)

    monkeypatch.setattr("services.item.CategoryRepository.get_or_create", _get_or_create)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_or_create", _get_or_create)

    items = await ItemService.parse_items_json(str(json_file), session=None)
    assert items[0].private_data == "AAAA-BBBB"
    assert items[0].delivery_image == "https://example.com/qr.png"
    # Kaunas items keep their data and photo: they are delivered like Panevezys ones.
    assert items[1].item_type == ItemType.PHYSICAL
    assert items[1].private_data == "PICKUP-CODE-1"
    assert items[1].delivery_image == "https://example.com/parcel.png"


@pytest.mark.asyncio
async def test_parse_items_json_treats_null_data_as_empty(tmp_path, monkeypatch):
    json_file = tmp_path / "items.json"
    json_file.write_text(
        """
        [
          {
            "item_type": "Physical",
            "category": "Merch",
            "subcategory": "Shirt",
            "price": 20,
            "description": "Tee",
            "private_data": null
          }
        ]
        """,
        encoding="utf-8",
    )

    async def _get_or_create(name, session):
        return SimpleNamespace(id=1, name=name)

    monkeypatch.setattr("services.item.CategoryRepository.get_or_create", _get_or_create)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_or_create", _get_or_create)

    items = await ItemService.parse_items_json(str(json_file), session=None)
    assert items[0].private_data is None
    assert items[0].delivery_image is None


@pytest.mark.asyncio
async def test_parse_items_txt_supports_optional_image_field(tmp_path, monkeypatch):
    txt_file = tmp_path / "items.txt"
    txt_file.write_text(
        "DIGITAL;Games;Steam;Key;10.0;CODE-1;https://example.com/qr.png\n"
        "DIGITAL;Games;Steam;Key;10.0;CODE-2\n",
        encoding="utf-8",
    )

    async def _get_or_create(name, session):
        return SimpleNamespace(id=1, name=name)

    monkeypatch.setattr("services.item.CategoryRepository.get_or_create", _get_or_create)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_or_create", _get_or_create)

    items = await ItemService.parse_items_txt(str(txt_file), session=None)
    assert items[0].private_data == "CODE-1"
    assert items[0].delivery_image == "https://example.com/qr.png"
    assert items[1].private_data == "CODE-2"
    assert items[1].delivery_image is None


@pytest.mark.asyncio
async def test_parse_items_txt_keeps_data_and_image_for_kaunas_items(tmp_path, monkeypatch):
    txt_file = tmp_path / "items.txt"
    txt_file.write_text(
        "PHYSICAL;Merch;Shirt;Tee;20.0;PICKUP-CODE-1;https://example.com/parcel.png\n"
        "PHYSICAL;Merch;Shirt;Tee;20.0;PICKUP-CODE-2\n"
        "PHYSICAL;Merch;Shirt;Tee;20.0;null\n",
        encoding="utf-8",
    )

    async def _get_or_create(name, session):
        return SimpleNamespace(id=1, name=name)

    monkeypatch.setattr("services.item.CategoryRepository.get_or_create", _get_or_create)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_or_create", _get_or_create)

    items = await ItemService.parse_items_txt(str(txt_file), session=None)
    assert [item.item_type for item in items] == [ItemType.PHYSICAL] * 3
    assert items[0].private_data == "PICKUP-CODE-1"
    assert items[0].delivery_image == "https://example.com/parcel.png"
    assert items[1].private_data == "PICKUP-CODE-2"
    assert items[1].delivery_image is None
    # "null" in the data column still means "no data attached".
    assert items[2].private_data is None


@pytest.mark.asyncio
async def test_deliver_purchased_items_sends_photo_with_code(monkeypatch):
    sent = []

    async def _send_photo(photo, caption, telegram_id, reply_markup=None):
        sent.append(("photo", photo, caption, telegram_id))

    async def _send_text(message, telegram_id, reply_markup=None):
        sent.append(("text", message, telegram_id))

    monkeypatch.setattr(NotificationService, "send_photo_to_user", _send_photo)
    monkeypatch.setattr(NotificationService, "send_to_user", _send_text)

    await NotificationService.deliver_purchased_items(
        telegram_id=42,
        items=[_item("STEAM-KEY-1", "https://example.com/qr.png")],
        language=Language.EN,
    )

    assert len(sent) == 1
    assert sent[0][0] == "photo"
    assert sent[0][1] == "https://example.com/qr.png"
    assert "STEAM-KEY-1" in sent[0][2]
    assert sent[0][3] == 42


@pytest.mark.asyncio
async def test_deliver_purchased_items_sends_kaunas_photo_and_data(monkeypatch):
    sent = []

    async def _send_photo(photo, caption, telegram_id, reply_markup=None):
        sent.append(("photo", photo, caption, telegram_id))

    async def _send_text(message, telegram_id, reply_markup=None):
        sent.append(("text", message, telegram_id))

    monkeypatch.setattr(NotificationService, "send_photo_to_user", _send_photo)
    monkeypatch.setattr(NotificationService, "send_to_user", _send_text)

    await NotificationService.deliver_purchased_items(
        telegram_id=42,
        items=[
            _kaunas_item("PICKUP-CODE-1", "kaunas-photo"),
            _kaunas_item("PICKUP-CODE-2"),
        ],
        language=Language.EN,
    )

    assert [kind for kind, *_ in sent] == ["photo", "text"]
    assert sent[0][1] == "kaunas-photo"
    assert "PICKUP-CODE-1" in sent[0][2]
    assert "PICKUP-CODE-2" in sent[1][1]


@pytest.mark.asyncio
async def test_deliver_purchased_items_falls_back_to_text_for_long_captions(monkeypatch):
    sent = []

    async def _send_photo(photo, caption, telegram_id, reply_markup=None):
        sent.append(("photo", photo, caption))

    async def _send_text(message, telegram_id, reply_markup=None):
        sent.append(("text", message))

    monkeypatch.setattr(NotificationService, "send_photo_to_user", _send_photo)
    monkeypatch.setattr(NotificationService, "send_to_user", _send_text)

    long_data = "K" * (MessageService.PHOTO_CAPTION_LIMIT + 1)
    await NotificationService.deliver_purchased_items(
        telegram_id=42,
        items=[_kaunas_item(long_data, "kaunas-photo")],
        language=Language.EN,
    )

    assert sent[0][0] == "photo"
    assert sent[0][2] == "📦 Your item"
    assert sent[1][0] == "text"
    assert long_data in sent[1][1]
