import re
from collections import OrderedDict

from enums.bot_entity import BotEntity
from enums.language import Language
from models.item import ItemDTO
from utils.utils import get_text


class MessageService:
    PHOTO_CAPTION_LIMIT = 1024
    IMAGE_URL_RE = re.compile(
        r"(https?://[^\s<>\"]+?\.(?:png|jpe?g|webp|gif)(?:\?[^\s<>\"]*)?)",
        re.IGNORECASE,
    )
    SKIP_IMAGE_VALUES = {"skip", "none", "-", "null", ""}

    @staticmethod
    def is_skip_delivery_image(value: str | None) -> bool:
        return (value or "").strip().lower() in MessageService.SKIP_IMAGE_VALUES

    @staticmethod
    def resolve_delivery_content(item: ItemDTO) -> tuple[str | None, str | None]:
        """Return (image, code) for a purchased item, no matter its item type.

        Items from every city (Panevezys and Kaunas) are delivered the same way.
        The image can be a Telegram file_id or an HTTPS URL stored on the item.
        If no dedicated image is set, an image URL embedded in private_data is used.
        """
        code = item.private_data
        image = item.delivery_image
        if image:
            return image, code
        if not code:
            return None, None
        match = MessageService.IMAGE_URL_RE.search(code)
        if match:
            url = match.group(1)
            remaining = f"{code[:match.start()]}{code[match.end():]}".strip()
            return url, remaining or None
        return None, code

    @staticmethod
    def create_message_with_codes(codes: list[str | None], language: Language, start: int = 1) -> str:
        message = "<b>"
        for count, code in enumerate(codes, start=start):
            message += get_text(language, BotEntity.USER, "purchased_item").format(
                count=count,
                private_data=code or ""
            )
        message += "</b>\n"
        return message

    @staticmethod
    def create_message_with_bought_items(items: list[ItemDTO], language: Language):
        codes = [MessageService.resolve_delivery_content(item)[1] for item in items]
        return MessageService.create_message_with_codes(codes, language)

    @staticmethod
    def build_delivery_groups(items: list[ItemDTO],
                              language: Language) -> list[tuple[str | None, str, list[ItemDTO]]]:
        """Group purchased items by delivery image and build (image, caption, items) payloads.

        Every item type is delivered the same way: the buyer receives the item data
        and, when the seller attached one, the delivery photo.
        """
        groups: OrderedDict[str, list[ItemDTO]] = OrderedDict()
        for item in items:
            image, _ = MessageService.resolve_delivery_content(item)
            groups.setdefault(image or "", []).append(item)
        deliveries: list[tuple[str | None, str, list[ItemDTO]]] = []
        count = 1
        for image_key, group_items in groups.items():
            codes = [MessageService.resolve_delivery_content(item)[1] for item in group_items]
            caption = MessageService.create_message_with_codes(codes, language, start=count)
            deliveries.append((image_key or None, caption, group_items))
            count += len(codes)
        return deliveries

    @staticmethod
    def build_delivery_messages(items: list[ItemDTO], language: Language) -> list[tuple[str | None, str]]:
        """Group purchased items by delivery image and build (image, caption) payloads."""
        return [(image, caption)
                for image, caption, _ in MessageService.build_delivery_groups(items, language)]
