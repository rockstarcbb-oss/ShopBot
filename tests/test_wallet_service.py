import pytest

from callbacks import MyProfileCallback
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from enums.language import Language
from services.user import UserService
from services.wallet import WalletService
from utils.utils import get_text


class _State:
    def __init__(self):
        self.cleared = False

    async def clear(self):
        self.cleared = True

    async def get_data(self):
        return {"cryptocurrency": Cryptocurrency.BTC.value}

    async def update_data(self, **kwargs):
        return None


class _Message:
    def __init__(self, text: str):
        self.text = text


@pytest.mark.asyncio
async def test_wallet_cancel_uses_localized_text():
    state = _State()
    message = _Message(get_text(Language.EN, BotEntity.COMMON, "cancel"))

    text, _ = await WalletService.calculate_withdrawal(message, state, Language.EN)

    assert state.cleared is True
    assert "Cancelled" in text


def test_wallet_validates_new_currency_addresses():
    assert WalletService.validate_withdrawal_address("D8BFXqDM7MHf3A4j3kC8wWEN8DqRLVQjax", Cryptocurrency.DOGE)


def test_wallet_rejects_empty_address_without_exception():
    assert WalletService.validate_withdrawal_address(None, Cryptocurrency.BTC) is False
    assert WalletService.validate_withdrawal_address("", Cryptocurrency.BTC) is False


def test_wallet_validates_btc_addresses():
    # Legacy P2PKH (starts with 1)
    assert WalletService.validate_withdrawal_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", Cryptocurrency.BTC)
    assert WalletService.validate_withdrawal_address("1BitcoinEaterAddressDontSendf59kuE", Cryptocurrency.BTC)
    # Legacy / Nested P2SH (starts with 3)
    assert WalletService.validate_withdrawal_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy", Cryptocurrency.BTC)
    # Native SegWit (Bech32)
    assert WalletService.validate_withdrawal_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq", Cryptocurrency.BTC)
    # Invalid addresses
    assert WalletService.validate_withdrawal_address("invalid_btc_address", Cryptocurrency.BTC) is False
    assert WalletService.validate_withdrawal_address("0x3be94a238ec30f2848e5a3e18251b14980c77f7f", Cryptocurrency.BTC) is False


def test_wallet_validates_ltc_addresses():
    # Legacy P2PKH (starts with L)
    assert WalletService.validate_withdrawal_address("LQL9pVH1LsMfKwt82Y2wGhNGkrjF8BRFox", Cryptocurrency.LTC)
    assert WalletService.validate_withdrawal_address("Lbu2oY3vxS5CdH87MW6PsWmpuDXb1zsn16", Cryptocurrency.LTC)
    # Legacy / P2SH (starts with M)
    assert WalletService.validate_withdrawal_address("MSvGuhWjF1y2Y5W4kYd5D8t6g3M8B2xZ1q", Cryptocurrency.LTC)
    # Legacy / P2SH (starts with 3)
    assert WalletService.validate_withdrawal_address("3CDJNfdHG8LuJnnTUGCb8VovTGYwZRNnnU", Cryptocurrency.LTC)
    # Native SegWit (Bech32)
    assert WalletService.validate_withdrawal_address("ltc1qg4df8e4yv9q7j2w3u4e5r6t7y8u9i0o1p2a3s4", Cryptocurrency.LTC)
    assert WalletService.validate_withdrawal_address("ltc1q8dg9mm2rmv96jlvncc6sdrpqd9p8nc2sagm4wr", Cryptocurrency.LTC)
    # Invalid addresses (the second one only differs from a valid LTC address
    # by a trailing '0' instead of '6' — base58 forbids '0')
    assert WalletService.validate_withdrawal_address("invalid_ltc_address", Cryptocurrency.LTC) is False
    assert WalletService.validate_withdrawal_address("Lbu2oY3vxS5CdH87MW6PsWmpuDXb1zsn10", Cryptocurrency.LTC) is False
    assert WalletService.validate_withdrawal_address("0x3be94a238ec30f2848e5a3e18251b14980c77f7f", Cryptocurrency.LTC) is False


@pytest.mark.asyncio
async def test_top_up_buttons_include_supported_currencies():
    _, keyboard = await UserService.get_top_up_buttons(
        MyProfileCallback.create(level=1),
        Language.EN
    )

    button_texts = [
        button.text
        for row in keyboard.as_markup().inline_keyboard
        for button in row
        if getattr(button, "text", None)
    ]

    assert "₿ BTC" in button_texts
    assert "USDT ERC-20" in button_texts


@pytest.mark.asyncio
async def test_admin_withdraw_menu_shows_supported_currencies(monkeypatch):
    async def _fake_wallet_balance():
        return {
            Cryptocurrency.BTC: 1.25,
            Cryptocurrency.USDT_ERC20: 20,
        }

    monkeypatch.setattr(
        "services.wallet.CryptoApiWrapper.get_wallet_balance",
        _fake_wallet_balance
    )

    text, keyboard = await WalletService.get_withdraw_menu(Language.EN)
    button_texts = [
        button.text
        for row in keyboard.as_markup().inline_keyboard
        for button in row
        if getattr(button, "text", None)
    ]

    assert "BTC" in text
    assert "USDT ERC20" in text
    assert "₿ BTC" in button_texts
    assert "USDT ERC-20" in button_texts
