import json
import logging
import math
import os
import re
import urllib.request
import datetime
from pathlib import Path

from jose import JWTError, jwt
from passlib.context import CryptContext
from pyngrok import ngrok

import config
from enums.bot_entity import BotEntity
from enums.language import Language
from utils.localizator import Localizator

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Used as a fallback everywhere a media file id is expected but the bot photo
# is not available (e.g. fresh install where startup has not cached it yet).
NO_IMAGE_URL = ("https://img.freepik.com/premium-vector/no-photo-available-vector-icon-default-image-symbol-"
                "picture-coming-soon-web-site-mobile-app_87543-18055.jpg")


# ADMIN_ID_LIST is set as a plain environment variable (Railway, Docker, .env),
# so the accepted separators are a comma, a semicolon and any whitespace.
# Brackets/parentheses and quotes are stripped as well, which lets a value
# copied from a Python list or a JSON array ("(111,222)", "[111, 222]",
# "\"111\",\"222\"") work unchanged.
ADMIN_ID_SEPARATOR_RE = re.compile(r"[,;\s]+")
ADMIN_ID_RE = re.compile(r"^\d+$")


def parse_admin_id_list(raw_value: str | None) -> list[int]:
    """
    Parse the raw ADMIN_ID_LIST environment value into a list of Telegram ids.

    All of the following are equivalent and produce [111, 222]:
        111,222
        (111,222)
        [111, 222]
        "111";"222"

    Duplicates are removed while the original order is preserved, and entries
    that are not plain positive integers are skipped with a warning, so a
    single typo cannot take the whole admin list down at startup.
    """
    if raw_value is None:
        return []
    normalized = re.sub(r"[\[\](){}<>]", " ", str(raw_value))
    normalized = normalized.replace('"', " ").replace("'", " ")
    admin_ids: list[int] = []
    for chunk in ADMIN_ID_SEPARATOR_RE.split(normalized):
        if not chunk:
            continue
        if ADMIN_ID_RE.match(chunk) is None:
            logging.warning("ADMIN_ID_LIST: '%s' is not a valid Telegram id and will be ignored", chunk)
            continue
        admin_id = int(chunk)
        if admin_id not in admin_ids:
            admin_ids.append(admin_id)
    return admin_ids


def build_admin_id_list(owner_ids: list[int], raw_value: str | None) -> list[int]:
    """
    Merge the ids that always keep admin access with the ones coming from the
    ADMIN_ID_LIST environment variable.

    The order of ``owner_ids`` is preserved, ids added through the environment
    are appended, and duplicates are dropped, so listing your own id in the
    variable is harmless.
    """
    admin_ids = list(owner_ids)
    for admin_id in parse_admin_id_list(raw_value):
        if admin_id not in admin_ids:
            admin_ids.append(admin_id)
    return admin_ids


def get_sslipio_external_url():
    external_ip = urllib.request.urlopen('https://api.ipify.org').read().decode('utf8')
    sslip_url = "https://" + external_ip + ".sslip.io"
    print("external URL: " + sslip_url)
    return sslip_url


def get_bot_photo_id() -> str:
    """
    Returns the cached telegram file id of the bot's "no image" photo.

    The cache file is written during startup (see MediaService.ensure_bot_photo).
    If it is missing (fresh clone, multibot mode, wiped working directory) a
    publicly available fallback image URL is returned instead of raising, so
    that flows like item/category creation keep working.
    """
    try:
        with open("static/no_image.jpeg", "r") as f:
            return f.read()
    except OSError:
        logging.warning("static/no_image.jpeg is missing or unreadable; "
                        "using the fallback image URL until the bot restarts")
        return NO_IMAGE_URL


def start_ngrok():
    ngrok_token = os.environ.get("NGROK_TOKEN")
    port = os.environ.get("WEBAPP_PORT")
    ngrok.set_auth_token(ngrok_token)
    http_tunnel = ngrok.connect(f":{port}", "http")
    return http_tunnel.public_url


def get_text(language: Language, entity: BotEntity, key: str) -> str:
    try:
        return Localizator.get_text(language, entity, key)
    except Exception as e:
        logging.error(e)
        if language == Language.EN:
            raise
        return Localizator.get_text(Language.EN, entity, key)


def remove_html_tags(text: str):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def calculate_max_page(records_qty: int):
    if records_qty % config.PAGE_ENTRIES == 0:
        return records_qty / config.PAGE_ENTRIES - 1
    else:
        return math.trunc(records_qty / config.PAGE_ENTRIES)


def extract_placeholders(text: str) -> set[str]:
    PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
    placeholders = set()
    for match in PLACEHOLDER_RE.findall(text):
        name = match.split(":", 1)[0]
        placeholders.add(name)
    return placeholders


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_i18n(reference_file: str = "en.json") -> None:
    folder_path = Path("./i18n")
    reference_path = folder_path / reference_file

    if not reference_path.exists():
        raise FileNotFoundError(f"Reference file not found: {reference_path}")

    reference = load_json(reference_path)
    errors = []

    for file_path in folder_path.glob("*.json"):
        if file_path.name == reference_file:
            continue

        data = load_json(file_path)

        for section, ref_keys in reference.items():
            if section not in data:
                errors.append(
                    f"[{file_path.name}] Missing section: '{section}'"
                )
                continue

            for key, ref_value in ref_keys.items():
                if key not in data[section]:
                    errors.append(
                        f"[{file_path.name}] Missing key: '{section}.{key}'"
                    )
                    continue

                if not isinstance(ref_value, str) or not isinstance(
                        data[section][key], str
                ):
                    continue

                ref_placeholders = extract_placeholders(ref_value)
                cur_placeholders = extract_placeholders(data[section][key])

                missing = ref_placeholders - cur_placeholders
                extra = cur_placeholders - ref_placeholders

                if missing:
                    errors.append(
                        f"[{file_path.name}] "
                        f"'{section}.{key}' missing placeholders: {sorted(missing)}"
                    )

                if extra:
                    errors.append(
                        f"[{file_path.name}] "
                        f"'{section}.{key}' extra placeholders: {sorted(extra)}"
                    )

    if errors:
        print("❌ Validation errors found:\n")
        for error in errors:
            print(error)
        raise SystemExit(1)

    print("✅ All localization files are valid")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)
