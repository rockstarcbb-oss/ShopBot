import importlib.util
import logging
import os
from pathlib import Path

import pytest

from utils.utils import build_admin_id_list, parse_admin_id_list


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    "raw_value,expected",
    [
        (None, []),
        ("", []),
        ("   ", []),
        ("123", [123]),
        ("123,456", [123, 456]),
        ("123, 456", [123, 456]),
        ("(123,456)", [123, 456]),
        ("(123, 456)", [123, 456]),
        ("[123,456]", [123, 456]),
        ("{123;456}", [123, 456]),
        ("<123,456>", [123, 456]),
        ('"123","456"', [123, 456]),
        ("'123';'456'", [123, 456]),
        ("123\n456", [123, 456]),
        ("123,456,", [123, 456]),
        (",123,,456,", [123, 456]),
        ("123,123,456", [123, 456]),
        ("1670676945,987654321", [1670676945, 987654321]),
    ],
)
def test_parse_admin_id_list_accepts_common_formats(raw_value, expected):
    assert parse_admin_id_list(raw_value) == expected


@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("123,abc,456", [123, 456]),
        ("-1,456", [456]),
        ("12.5,456", [456]),
        ("@username,456", [456]),
        ("abc", []),
    ],
)
def test_parse_admin_id_list_skips_invalid_entries(raw_value, expected, caplog):
    with caplog.at_level(logging.WARNING):
        assert parse_admin_id_list(raw_value) == expected

    assert "is not a valid Telegram id" in caplog.text


def test_parse_admin_id_list_does_not_warn_for_valid_value(caplog):
    with caplog.at_level(logging.WARNING):
        assert parse_admin_id_list("(123,456)") == [123, 456]

    assert caplog.text == ""


def test_build_admin_id_list_appends_env_ids_to_owner_ids():
    owner_ids = [111]

    assert build_admin_id_list(owner_ids, "(222,333)") == [111, 222, 333]


def test_build_admin_id_list_without_env_value_keeps_owner_ids():
    assert build_admin_id_list([111], None) == [111]
    assert build_admin_id_list([111], "  ") == [111]


def test_build_admin_id_list_drops_duplicates_and_ignores_garbage():
    assert build_admin_id_list([111, 222], "222,junk,333") == [111, 222, 333]


def test_build_admin_id_list_does_not_mutate_owner_ids():
    owner_ids = [111]

    build_admin_id_list(owner_ids, "222")

    assert owner_ids == [111]


def _load_real_config(monkeypatch, env: dict):
    """Import config.py as a fresh module with the given environment."""
    for key in list(os.environ):
        if key.startswith(("ADMIN_ID_LIST", "WEBHOOK_HOST", "WEBHOOK_URL")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("WEBHOOK_HOST", "https://example.com")
    monkeypatch.setenv("SQLADMIN_RAW_PASSWORD", "password")
    monkeypatch.setenv("RUNTIME_ENVIRONMENT", "production")
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    module_name = f"real_config_{abs(hash(tuple(sorted(env.items()))))}"
    spec = importlib.util.spec_from_file_location(module_name, PROJECT_ROOT / "config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "env,extra_ids",
    [
        ({"ADMIN_ID_LIST": "222,333"}, [222, 333]),
        ({"ADMIN_ID_LIST": "(222,333)"}, [222, 333]),
        ({"ADMIN_ID_LIST": "[222, 333]"}, [222, 333]),
        ({"ADMIN_ID_LIST": '"222";"333"'}, [222, 333]),
        ({"ADMIN_ID_LIST": "222,junk,333"}, [222, 333]),
        ({"ADMIN_ID_LIST": ""}, []),
        ({}, []),
    ],
)
def test_config_reads_admin_id_list_from_environment(monkeypatch, env, extra_ids):
    config_module = _load_real_config(monkeypatch, env)

    # The owner id from config.py always comes first, env ids are appended.
    assert config_module.ADMIN_ID_LIST == [*config_module.OWNER_ADMIN_ID_LIST, *extra_ids]
    assert config_module.ADMIN_ID_LIST[0] == 1670676945


def test_config_deduplicates_owner_id_from_environment(monkeypatch):
    config_module = _load_real_config(monkeypatch, {"ADMIN_ID_LIST": "1670676945,222"})

    assert config_module.ADMIN_ID_LIST == [1670676945, 222]
