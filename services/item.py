from json import load

from aiogram.types import InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import AllCategoriesCallback
from db import session_commit
from enums.add_type import AddType
from enums.announcement_type import AnnouncementType
from enums.bot_entity import BotEntity
from enums.item_type import ItemType
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from models.item import ItemDTO
from repositories.button_media import ButtonMediaRepository
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from services.media import MediaService
from services.message import MessageService
from utils.utils import get_text


class ItemService:
    ANNOUNCEMENT_MESSAGE_LIMIT = 4000
    # Values used in JSON/TXT imports to say "this item has no data attached".
    EMPTY_DATA_VALUES = {"", "null", "none", "-"}

    @staticmethod
    def normalize_private_data(value: str | None) -> str | None:
        if value is None:
            return None
        return None if value.strip().lower() in ItemService.EMPTY_DATA_VALUES else value

    @staticmethod
    def _wrap_announcement_chunk(content: str) -> str:
        return f"<b>{content}</b>"

    @staticmethod
    def _split_category_into_blocks(header: str,
                                    category_header: str,
                                    subcategory_lines: list[str]) -> list[str]:
        max_content_length = ItemService.ANNOUNCEMENT_MESSAGE_LIMIT - len("<b></b>")
        category_blocks: list[str] = []
        current_block = category_header
        for line in subcategory_lines:
            if len(header + current_block + line) <= max_content_length:
                current_block += line
                continue
            if current_block != category_header:
                category_blocks.append(current_block)
                current_block = category_header + line
            else:
                category_blocks.append(current_block + line)
                current_block = category_header
        if current_block != category_header or not category_blocks:
            category_blocks.append(current_block)
        return category_blocks

    @staticmethod
    def _build_announcement_chunks(header: str, category_blocks: list[str]) -> list[str]:
        max_content_length = ItemService.ANNOUNCEMENT_MESSAGE_LIMIT - len("<b></b>")
        chunks: list[str] = []
        current_content = header
        for block in category_blocks:
            if len(current_content + block) <= max_content_length:
                current_content += block
                continue
            if current_content != header:
                chunks.append(ItemService._wrap_announcement_chunk(current_content))
            current_content = header + block
        if current_content == header and chunks:
            return chunks
        chunks.append(ItemService._wrap_announcement_chunk(current_content))
        return chunks

    @staticmethod
    async def create_announcement_message(announcement_type: AnnouncementType,
                                          session: AsyncSession,
                                          language: Language) -> list[str]:
        if announcement_type == AnnouncementType.CURRENT_STOCK:
            items = await ItemRepository.get_in_stock(session)
            header = get_text(language, BotEntity.ADMIN, "current_stock_header")
        else:
            items = await ItemRepository.get_new(session)
            header = get_text(language, BotEntity.ADMIN, "restocking_message_header")
        filtered_items = {}
        category_map = {
            category.id: category
            for category in await CategoryRepository.get_by_ids(
                [item.category_id for item in items],
                session
            )
        }
        subcategory_map = {
            subcategory.id: subcategory
            for subcategory in await SubcategoryRepository.get_by_ids(
                [item.subcategory_id for item in items],
                session
            )
        }
        for item in items:
            category = category_map[item.category_id]
            subcategory = subcategory_map[item.subcategory_id]
            if category.name not in filtered_items:
                filtered_items[category.name] = {}
            if subcategory.name not in filtered_items[category.name]:
                filtered_items[category.name][subcategory.name] = []
            filtered_items[category.name][subcategory.name].append(item)
        category_blocks = []
        for category, subcategory_item_dict in filtered_items.items():
            category_header = get_text(language, BotEntity.ADMIN, "restocking_message_category").format(
                category=category
            )
            subcategory_lines = []
            for subcategory, item in subcategory_item_dict.items():
                subcategory_lines.append(get_text(language, BotEntity.USER, "subcategory_button").format(
                    subcategory_name=subcategory,
                    available_quantity=len(item),
                    subcategory_price=item[0].price,
                    currency_sym=config.CURRENCY.get_localized_symbol()) + "\n")
            category_blocks.extend(
                ItemService._split_category_into_blocks(header, category_header, subcategory_lines)
            )
        return ItemService._build_announcement_chunks(header, category_blocks)

    @staticmethod
    async def parse_items_json(path_to_file: str, session: AsyncSession | Session):
        with open(path_to_file, 'r', encoding='utf-8') as file:
            items = load(file)
            items_list = []
            for item in items:
                item_type = ItemType.parse(item['item_type'])
                category = await CategoryRepository.get_or_create(item['category'], session)
                subcategory = await SubcategoryRepository.get_or_create(item['subcategory'], session)
                item.pop('item_type')
                item.pop('category')
                item.pop('subcategory')
                # Items from every city are delivered the same way, so the data and
                # the delivery photo are kept for both item types.
                item['private_data'] = ItemService.normalize_private_data(item.get('private_data'))
                if not item.get('delivery_image'):
                    item['delivery_image'] = None
                items_list.append(ItemDTO(
                    item_type=item_type,
                    category_id=category.id,
                    subcategory_id=subcategory.id,
                    **item
                ))
            return items_list

    @staticmethod
    async def parse_items_txt(path_to_file: str, session: AsyncSession | Session):
        with open(path_to_file, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            items_list = []
            for line in lines:
                raw_line = line.strip()
                if not raw_line:
                    continue
                parts = raw_line.split(';')
                item_type, category_name, subcategory_name, description, price, private_data = parts[:6]
                private_data = ItemService.normalize_private_data(private_data)
                delivery_image = parts[6] if len(parts) > 6 else None
                if MessageService.is_skip_delivery_image(delivery_image):
                    delivery_image = None
                item_type = ItemType.parse(item_type)
                category = await CategoryRepository.get_or_create(category_name, session)
                subcategory = await SubcategoryRepository.get_or_create(subcategory_name, session)
                items_list.append(ItemDTO(
                    item_type=item_type,
                    category_id=category.id,
                    subcategory_id=subcategory.id,
                    price=float(price),
                    description=description,
                    private_data=private_data,
                    delivery_image=delivery_image
                ))
            return items_list

    @staticmethod
    async def add_items(path_to_file: str,
                        add_type: AddType,
                        session: AsyncSession | Session,
                        language: Language) -> str:
        try:
            if add_type == AddType.JSON:
                items_list = await ItemService.parse_items_json(path_to_file, session)
            else:
                items_list = await ItemService.parse_items_txt(path_to_file, session)
            await ItemRepository.add_many(items_list, session)
            await session_commit(session)
            return get_text(language, BotEntity.ADMIN, "add_items_success").format(
                adding_result=len(items_list)
            )
        except Exception as exception:
            return get_text(language, BotEntity.ADMIN, "add_items_err").format(
                adding_result=exception
            )

    @staticmethod
    async def get_all_types(callback_data: AllCategoriesCallback,
                            session: AsyncSession,
                            language: Language) -> tuple[InputMediaPhoto, InlineKeyboardBuilder]:
        callback_data = callback_data or AllCategoriesCallback.create(0)
        kb_builder = InlineKeyboardBuilder()
        # Both city buttons (Panevezys and Kaunas) are always shown, even when the
        # city has no in-stock items right now. The "empty city" case is handled on
        # the next screen (see CategoryService.get_buttons).
        for item_type in ItemType:
            kb_builder.button(
                text=item_type.get_localized(language),
                callback_data=callback_data.model_copy(update={"level": callback_data.level + 1,
                                                               "item_type": item_type})
            )
        kb_builder.adjust(1)
        caption = get_text(language, BotEntity.USER, "pick_item_type")
        button_media = await ButtonMediaRepository.get_by_button(
            KeyboardButton.ALL_CATEGORIES, session
        )
        return MediaService.convert_to_media(button_media.media_id, caption=caption), kb_builder

