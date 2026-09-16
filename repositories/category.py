from sqlalchemy import select, func, update, or_, and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from db import get_db_session, session_commit, session_execute, session_flush
from enums.item_type import ItemType
from enums.sort_order import SortOrder
from enums.sort_property import SortProperty
from models.category import Category, CategoryDTO
from models.item import Item
from utils.utils import get_bot_photo_id, calculate_max_page


# Shared categories are visible in both city catalogues, regardless of stock.
PERMANENT_CATEGORY_NAMES = ("Cartukai 🛒",)


class CategoryRepository:
    @staticmethod
    async def init_permanent_categories():
        async with get_db_session() as session:
            for name in PERMANENT_CATEGORY_NAMES:
                # Preserve existing categories, IDs and media; safe on repeated startup.
                stmt = (insert(Category)
                        .values(name=name, media_id=f"0{get_bot_photo_id()}")
                        .on_conflict_do_nothing(index_elements=[Category.name]))
                await session_execute(stmt, session)
            await session_commit(session)

    @staticmethod
    def _catalogue_query(filters, item_type, include_permanent=True):
        stock_conditions = [Item.category_id == Category.id, Item.is_sold == False]
        if item_type is not None:
            stock_conditions.append(Item.item_type == item_type)
        visible = Item.id.is_not(None)
        if include_permanent:
            visible = or_(Category.name.in_(PERMANENT_CATEGORY_NAMES), visible)
        stmt = select(Category).outerjoin(Item, and_(*stock_conditions)).where(visible)
        if filters:
            stmt = stmt.where(or_(*(Category.name.icontains(name) for name in filters)))
        return stmt.distinct()

    @staticmethod
    async def get(sort_pairs: dict[str, int],
                  filters: list[str] | None,
                  item_type: ItemType | None,
                  page: int,
                  session: AsyncSession) -> list[CategoryDTO]:
        sort_methods = []
        for sort_property, sort_order in sort_pairs.items():
            sort_property, sort_order = SortProperty(int(sort_property)), SortOrder(sort_order)
            if sort_order != SortOrder.DISABLE:
                table = Category if sort_property == SortProperty.NAME else Item
                sort_column = sort_property.get_column(table)
                sort_method = (getattr(sort_column, sort_order.name.lower()))
                sort_methods.append(sort_method())
        stmt = (CategoryRepository._catalogue_query(filters, item_type)
                .limit(config.PAGE_ENTRIES)
                .offset(page * config.PAGE_ENTRIES)
                .order_by(*sort_methods, Category.id))
        category_names = await session_execute(stmt, session)
        categories = category_names.scalars().all()
        return [CategoryDTO.model_validate(category, from_attributes=True) for category in categories]

    @staticmethod
    async def get_maximum_page(filters: list[str] | None, session: AsyncSession,
                               item_type: ItemType | None = None,
                               include_permanent: bool = True) -> int:
        sub_stmt = CategoryRepository._catalogue_query(filters, item_type, include_permanent).subquery()
        stmt = select(func.count()).select_from(sub_stmt)
        result = await session_execute(stmt, session)
        return calculate_max_page(result.scalar_one())

    @staticmethod
    async def get_by_id(category_id: int, session: Session | AsyncSession) -> CategoryDTO:
        stmt = select(Category).where(Category.id == category_id)
        category = await session_execute(stmt, session)
        return CategoryDTO.model_validate(category.scalar(), from_attributes=True)

    @staticmethod
    async def get_to_delete(sort_pairs: dict[str, int],
                            filters: list[str],
                            page: int, session: AsyncSession) -> list[CategoryDTO]:
        sort_methods = []
        for sort_property, sort_order in sort_pairs.items():
            sort_property, sort_order = SortProperty(int(sort_property)), SortOrder(sort_order)
            if sort_order != SortOrder.DISABLE:
                sort_column = sort_property.get_column(Category)
                sort_method = (getattr(sort_column, sort_order.name.lower()))
                sort_methods.append(sort_method())
        conditions = [
            Item.is_sold == False
        ]
        if filters is not None:
            filter_conditions = [Category.name.icontains(name) for name in filters]
            conditions.append(or_(*filter_conditions))
        stmt = (select(Category)
                .join(Item, Item.category_id == Category.id)
                .where(*conditions)
                .distinct()
                .limit(config.PAGE_ENTRIES)
                .offset(page * config.PAGE_ENTRIES)
                .order_by(*sort_methods))
        categories = await session_execute(stmt, session)
        return [CategoryDTO.model_validate(category, from_attributes=True) for category in
                categories.scalars().all()]

    @staticmethod
    async def get_or_create(category_name: str, session: Session | AsyncSession) -> CategoryDTO:
        stmt = select(Category).where(Category.name == category_name)
        category = await session_execute(stmt, session)
        category = category.scalar()
        if category is None:
            bot_photo_id = get_bot_photo_id()
            new_category_obj = Category(name=category_name, media_id=f"0{bot_photo_id}")
            session.add(new_category_obj)
            await session_flush(session)
            category = new_category_obj
        return CategoryDTO.model_validate(category, from_attributes=True)

    @staticmethod
    async def get_by_ids(category_ids: list[int], session: Session | AsyncSession) -> list[CategoryDTO]:
        if not category_ids:
            return []
        stmt = select(Category).where(Category.id.in_(category_ids))
        categories = await session_execute(stmt, session)
        return [CategoryDTO.model_validate(category, from_attributes=True) for category in categories.scalars().all()]

    @staticmethod
    async def update(category_dto: CategoryDTO, session: AsyncSession):
        stmt = (update(Category)
                .where(Category.id == category_dto.id)
                .values(**category_dto.model_dump()))
        await session_execute(stmt, session)
