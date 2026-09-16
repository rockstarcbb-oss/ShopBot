from types import SimpleNamespace

import pytest
from aiogram.types import InputMediaAnimation, InputMediaPhoto, InputMediaVideo
from sqlalchemy.exc import NoResultFound

from callbacks import MediaManagementCallback
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from models.button_media import ButtonMediaDTO
from services.media import MediaService
from utils.utils import get_text
from enums.bot_entity import BotEntity


def test_start_message_is_a_managed_media_slot():
    assert KeyboardButton.START_MESSAGE in list(KeyboardButton)


@pytest.mark.parametrize("language", [Language.EN, Language.LT, Language.RU])
def test_start_message_has_a_localized_label(language):
    label = get_text(language, BotEntity.USER, KeyboardButton.START_MESSAGE.value.lower())

    assert label
    assert "{entity" not in label


@pytest.mark.asyncio
async def test_media_menu_offers_start_message_edit_button():
    text, kb_builder = await MediaService.get_menu(MediaManagementCallback.create(level=0), Language.EN)
    buttons = [button for row in kb_builder.as_markup().inline_keyboard for button in row]

    start_buttons = [button for button in buttons if "START_MESSAGE" in (button.callback_data or "")]

    assert len(start_buttons) == 1
    assert get_text(Language.EN, BotEntity.USER, "start_message") in start_buttons[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "media_id,expected_type,expected_file_id",
    [
        ("0PHOTOFILEID", InputMediaPhoto, "PHOTOFILEID"),
        ("1VIDEOFILEID", InputMediaVideo, "VIDEOFILEID"),
        ("2GIFFILEID", InputMediaAnimation, "GIFFILEID"),
    ],
)
async def test_get_greeting_media_uses_the_stored_media(monkeypatch, media_id, expected_type, expected_file_id):
    async def _get_by_button(button, session):
        assert button == KeyboardButton.START_MESSAGE
        return ButtonMediaDTO(id=1, media_id=media_id, button=button)

    monkeypatch.setattr("services.media.ButtonMediaRepository.get_by_button", _get_by_button)

    media = await MediaService.get_greeting_media(Language.EN, session=None)

    assert isinstance(media, expected_type)
    assert media.media == expected_file_id
    assert media.caption == get_text(Language.EN, BotEntity.COMMON, "start_message")


@pytest.mark.asyncio
async def test_get_greeting_media_falls_back_to_the_bot_photo(monkeypatch):
    async def _missing(button, session):
        raise NoResultFound()

    monkeypatch.setattr("services.media.ButtonMediaRepository.get_by_button", _missing)
    monkeypatch.setattr("services.media.get_bot_photo_id", lambda: "FALLBACKPHOTO")

    media = await MediaService.get_greeting_media(Language.EN, session=None)

    assert isinstance(media, InputMediaPhoto)
    assert media.media == "FALLBACKPHOTO"


@pytest.mark.asyncio
async def test_admin_can_replace_the_start_message_media(monkeypatch):
    stored = ButtonMediaDTO(id=1, media_id="0OLDPHOTO", button=KeyboardButton.START_MESSAGE)
    updated = []

    async def _get_by_button(button, session):
        return stored

    async def _update(dto, session):
        updated.append(dto)

    async def _noop_edit(*args, **kwargs):
        return None

    monkeypatch.setattr("services.media.ButtonMediaRepository.get_by_button", _get_by_button)
    monkeypatch.setattr("services.media.ButtonMediaRepository.update", _update)
    monkeypatch.setattr("services.media.NotificationService.edit_reply_markup", _noop_edit)

    state = SimpleNamespace(
        get_data=lambda: _awaitable({"chat_id": 1, "msg_id": 2, "keyboard_button": "START_MESSAGE"}),
        clear=lambda: _awaitable(None),
    )
    message = SimpleNamespace(
        bot=object(),
        photo=[SimpleNamespace(file_id="NEWPHOTO")],
        video=None,
        animation=None,
    )

    text, kb_builder = await MediaService.receive_new_entity_media(message, state, session=None,
                                                                   language=Language.EN)

    assert updated[0].media_id == "0NEWPHOTO"
    assert updated[0].button == KeyboardButton.START_MESSAGE
    assert get_text(Language.EN, BotEntity.USER, "start_message") in text


def _awaitable(result):
    async def _coro():
        return result

    return _coro()
