import pytest

from enums.item_type import ItemType
from enums.language import Language


def test_parse_accepts_raw_values_in_any_case():
    assert ItemType.parse("DIGITAL") == ItemType.DIGITAL
    assert ItemType.parse("digital") == ItemType.DIGITAL
    assert ItemType.parse(" Physical ") == ItemType.PHYSICAL
    assert ItemType.parse("PHYSICAL") == ItemType.PHYSICAL


def test_parse_accepts_the_city_labels_shown_in_the_bot():
    """Admins see cities (Panevezys / Kaunas), so those names are accepted too."""
    assert ItemType.parse("Panevezys") == ItemType.DIGITAL
    assert ItemType.parse("Panevėžys") == ItemType.DIGITAL
    assert ItemType.parse("Kaunas") == ItemType.PHYSICAL
    assert ItemType.parse("💾 Panevezys") == ItemType.DIGITAL
    assert ItemType.parse("🏷️ Kaunas") == ItemType.PHYSICAL


@pytest.mark.parametrize("language", list(Language))
def test_parse_accepts_every_localized_label(language):
    for item_type in ItemType:
        assert ItemType.parse(item_type.get_localized(language)) == item_type


def test_parse_rejects_unknown_values():
    with pytest.raises(ValueError):
        ItemType.parse("Vilnius")
    with pytest.raises(ValueError):
        ItemType.parse("")
    with pytest.raises(ValueError):
        ItemType.parse(None)
