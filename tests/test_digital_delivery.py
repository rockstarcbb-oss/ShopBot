from types import SimpleNamespace

import pytest

from enums.item_type import ItemType
from enums.language import Language
from models.item import ItemDTO
from services.item import ItemService
from services.message import MessageService
from services.notification import NotificationService


def _digital_item(private_data: str | None, delivery_image: str | None = None) -> ItemDTO:
    return ItemDTO(
        item_type=ItemType.DIGITAL,
        private_data=private_data,
        delivery_image=delivery_image,
    )


def test_resolve_delivery_content_uses_stored_image():
    image, code = MessageService.resolve_delivery_content(
        _digital_item("GAME-CODE-123", "https://cdn.example.com/qr.png")
    )
    assert image == "https://cdn.example.com/qr.png"
    assert code == "GAME-CODE-123"


def test_resolve_delivery_content_extracts_image_url_from_private_data():
    image, code = MessageService.resolve_delivery_content(
        _digital_item("https://cdn.example.com/qr.jpg GAME-CODE-123")
    )
    assert image == "https://cdn.example.com/qr.jpg"
    assert code == "GAME-CODE-123"


def test_resolve_delivery_content_keeps_plain_code():
    image, code = MessageService.resolve_delivery_content(_digital_item("XXXX-YYYY"))
    assert image is None
    assert code == "XXXX-YYYY"


def test_build_digital_delivery_messages_groups_same_image():
    items = [
        _digital_item("CODE-1", "file-id-1"),
        _digital_item("CODE-2", "file-id-1"),
        _digital_item("CODE-3"),
    ]
    deliveries = MessageService.build_digital_delivery_messages(items, Language.EN)
    assert len(deliveries) == 2
    assert deliveries[0][0] == "file-id-1"
    assert "CODE-1" in deliveries[0][1]
    assert "CODE-2" in deliveries[0][1]
    assert deliveries[1][0] is None
    assert "CODE-3" in deliveries[1][1]


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
            "private_data": null,
            "delivery_image": "https://example.com/should-be-ignored.png"
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
    assert items[1].private_data is None
    assert items[1].delivery_image is None


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
async def test_deliver_digital_items_sends_photo_with_code(monkeypatch):
    sent = []

    async def _send_photo(photo, caption, telegram_id, reply_markup=None):
        sent.append(("photo", photo, caption, telegram_id))

    async def _send_text(message, telegram_id, reply_markup=None):
        sent.append(("text", message, telegram_id))

    monkeypatch.setattr(NotificationService, "send_photo_to_user", _send_photo)
    monkeypatch.setattr(NotificationService, "send_to_user", _send_text)

    await NotificationService.deliver_digital_items(
        telegram_id=42,
        items=[_digital_item("STEAM-KEY-1", "https://example.com/qr.png")],
        language=Language.EN,
    )

    assert len(sent) == 1
    assert sent[0][0] == "photo"
    assert sent[0][1] == "https://example.com/qr.png"
    assert "STEAM-KEY-1" in sent[0][2]
    assert sent[0][3] == 42
