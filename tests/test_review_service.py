from types import SimpleNamespace

import pytest

from callbacks import ReviewManagementCallback
from enums.bot_entity import BotEntity
from enums.language import Language
from enums.user_role import UserRole
from services.review import ReviewService
from utils.utils import get_text


class _State:
    def __init__(self, data):
        self._data = data
        self.cleared = False

    async def get_data(self):
        return dict(self._data)

    async def clear(self):
        self.cleared = True


class _Session:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_review_confirmation_uses_subcategory_id(monkeypatch):
    callback_data = ReviewManagementCallback.create(level=4, buy_id=1, buyItem_id=2, rating=5)
    requested_subcategory_ids = []

    async def _fake_get_buy_item(*args, **kwargs):
        return SimpleNamespace(item_ids=[9])

    async def _fake_get_item(*args, **kwargs):
        return SimpleNamespace(category_id=11, subcategory_id=77, price=15.0, item_type=SimpleNamespace(
            get_localized=lambda language: "Digital"
        ))

    async def _fake_get_category(*args, **kwargs):
        return SimpleNamespace(name="Category")

    async def _fake_get_subcategory(subcategory_id, *args, **kwargs):
        requested_subcategory_ids.append(subcategory_id)
        return SimpleNamespace(name="Subcategory")

    monkeypatch.setattr("services.review.BuyItemRepository.get_by_id", _fake_get_buy_item)
    monkeypatch.setattr("services.review.ItemRepository.get_by_id", _fake_get_item)
    monkeypatch.setattr("services.review.CategoryRepository.get_by_id", _fake_get_category)
    monkeypatch.setattr("services.review.SubcategoryRepository.get_by_id", _fake_get_subcategory)
    monkeypatch.setattr("services.review.get_bot_photo_id", lambda: "bot-photo-id")

    await ReviewService.review_confirmation(callback_data, _State({"review_text": "ok"}), session=None, language=Language.EN)

    assert requested_subcategory_ids == [77]


@pytest.mark.asyncio
async def test_create_review_checks_duplicate_by_buy_item_id(monkeypatch):
    callback_data = ReviewManagementCallback.create(level=4, buy_id=1, buyItem_id=22, review_id=999, rating=5)
    requested_ids = []

    async def _fake_get_by_buy_item_id(buy_item_id, *args, **kwargs):
        requested_ids.append(buy_item_id)
        return SimpleNamespace(id=1, buyItem_id=buy_item_id)

    async def _fake_new_review_published(*args, **kwargs):
        return None

    monkeypatch.setattr("services.review.ReviewRepository.get_by_buy_item_id", _fake_get_by_buy_item_id)
    monkeypatch.setattr("services.review.NotificationService.new_review_published", _fake_new_review_published)
    monkeypatch.setattr("services.review.get_bot_photo_id", lambda: "bot-photo-id")

    media, _ = await ReviewService.create_review(
        callback_data,
        _State({"review_text": "ok"}),
        session=_Session(),
        language=Language.EN
    )

    assert requested_ids == [22]
    assert media.caption


def _review(id_=99, image_id="photo-1"):
    return SimpleNamespace(id=id_, buyItem_id=2, text="Great item",
                           image_id=image_id, rating=5)


def _item_dto():
    return SimpleNamespace(category_id=1, subcategory_id=2, price=20.0,
                           item_type=SimpleNamespace(get_localized=lambda language: "Digital"))


def _patch_review_single_dependencies(monkeypatch, review):
    async def _get_review_by_id(review_id, session):
        return review

    async def _get_buy_item(buy_item_id, session):
        return SimpleNamespace(id=2, buy_id=7, item_ids=[9])

    async def _get_item(item_id, session):
        return _item_dto()

    async def _get_category(category_id, session):
        return SimpleNamespace(id=1, name="Category")

    async def _get_subcategory(subcategory_id, session):
        return SimpleNamespace(id=2, name="Subcategory")

    async def _get_buy(buy_id, session):
        return SimpleNamespace(id=7, buyer_id=3)

    async def _get_user(user_id, session):
        return SimpleNamespace(id=3, telegram_id=42, telegram_username="buyer")

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("services.review.ReviewRepository.get_by_id", _get_review_by_id)
    monkeypatch.setattr("services.review.BuyItemRepository.get_by_id", _get_buy_item)
    monkeypatch.setattr("services.review.ItemRepository.get_by_id", _get_item)
    monkeypatch.setattr("services.review.CategoryRepository.get_by_id", _get_category)
    monkeypatch.setattr("services.review.SubcategoryRepository.get_by_id", _get_subcategory)
    monkeypatch.setattr("services.review.BuyRepository.get_by_id", _get_buy)
    monkeypatch.setattr("services.review.UserRepository.get_user_entity", _get_user)
    monkeypatch.setattr("services.review.NotificationService.add_user_button", _noop)
    monkeypatch.setattr("services.review.get_bot_photo_id", lambda: "bot-photo-id")


@pytest.mark.asyncio
async def test_view_review_single_offers_delete_for_admin(monkeypatch):
    review = _review()
    _patch_review_single_dependencies(monkeypatch, review)
    callback_data = ReviewManagementCallback.create(level=6, review_id=99, buy_id=7,
                                                    buyItem_id=2, user_role=UserRole.ADMIN)

    _media, kb_builder = await ReviewService.view_review_single(callback_data, session=None, language=Language.EN)

    buttons = [button for row in kb_builder.as_markup().inline_keyboard for button in row]
    delete_button = next(button for button in buttons
                         if button.text == get_text(Language.EN, BotEntity.ADMIN, "delete_review"))
    packed = ReviewManagementCallback.unpack(delete_button.callback_data)
    assert packed.level == 9
    assert packed.confirmation is False


@pytest.mark.asyncio
async def test_delete_review_removes_review_for_admin(monkeypatch):
    deleted_ids = []
    session = _Session()

    async def _fake_delete(review_id, session):
        deleted_ids.append(review_id)

    monkeypatch.setattr("services.review.ReviewRepository.delete", _fake_delete)
    monkeypatch.setattr("services.review.get_bot_photo_id", lambda: "bot-photo-id")

    callback = SimpleNamespace(from_user=SimpleNamespace(id=1))
    callback_data = ReviewManagementCallback.create(level=9, review_id=99, buy_id=7,
                                                    buyItem_id=2, user_role=UserRole.ADMIN,
                                                    confirmation=True)

    media, kb_builder = await ReviewService.delete_review(callback, callback_data,
                                                          session=session, language=Language.EN)

    assert deleted_ids == [99]
    assert session.commits == 1
    assert media.caption == get_text(Language.EN, BotEntity.ADMIN, "review_deleted")
    buttons = [button for row in kb_builder.as_markup().inline_keyboard for button in row]
    assert len(buttons) == 1
    packed = ReviewManagementCallback.unpack(buttons[0].callback_data)
    assert packed.level == 5
    assert packed.user_role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_delete_review_ignored_for_non_admin(monkeypatch):
    deleted_ids = []
    session = _Session()

    async def _fake_delete(review_id, session):
        deleted_ids.append(review_id)

    review = _review()
    _patch_review_single_dependencies(monkeypatch, review)
    monkeypatch.setattr("services.review.ReviewRepository.delete", _fake_delete)
    monkeypatch.setattr("services.review.get_bot_photo_id", lambda: "bot-photo-id")

    callback = SimpleNamespace(from_user=SimpleNamespace(id=999))
    callback_data = ReviewManagementCallback.create(level=9, review_id=99, buy_id=7,
                                                    buyItem_id=2, user_role=UserRole.ADMIN,
                                                    confirmation=True)

    media, kb_builder = await ReviewService.delete_review(callback, callback_data,
                                                          session=session, language=Language.EN)

    assert deleted_ids == []
    assert session.commits == 0
    assert media.caption and "Category" in media.caption  # falls back to the single review view
