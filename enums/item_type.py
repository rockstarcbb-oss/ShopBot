import re
from enum import Enum

from enums.bot_entity import BotEntity
from enums.language import Language
from utils.utils import get_text

_NON_WORD_RE = re.compile(r"\W+", re.UNICODE)


class ItemType(Enum):
    DIGITAL = "DIGITAL"
    PHYSICAL = "PHYSICAL"

    def get_localized(self, language: Language):
        return get_text(language, BotEntity.COMMON, self.value.lower())

    @staticmethod
    def _normalize(value: str | None) -> str:
        """Drop emoji, spaces and punctuation so labels can be compared reliably."""
        return _NON_WORD_RE.sub("", value or "").upper()

    @classmethod
    def parse(cls, raw_value: str | None) -> 'ItemType':
        """Resolve an item type written by an admin or stored in an import file.

        Besides the raw values (`DIGITAL`, `PHYSICAL`) the city labels shown
        inside the bot are accepted as well - in any language, with or without
        their emoji (for example `Panevezys`, `Panevėžys` or `Kaunas`).
        Raises ValueError when nothing matches.
        """
        normalized = cls._normalize(raw_value)
        if not normalized:
            raise ValueError("Item type is empty")
        for item_type in cls:
            if normalized == cls._normalize(item_type.value):
                return item_type
        for item_type in cls:
            for language in Language:
                if normalized == cls._normalize(get_text(language, BotEntity.COMMON, item_type.value.lower())):
                    return item_type
        raise ValueError(f"Unknown item type: {raw_value!r}")
