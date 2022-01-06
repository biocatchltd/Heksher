from logging import getLogger
from typing import AbstractSet, Iterable, Mapping, Optional, Sequence, Tuple

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from heksher.db_logic.metadata import configurable, context_features

logger = getLogger(__name__)


async def db_move_context_features(conn: AsyncConnection, new_indices: Mapping[str, int]):
    """
    Update the indices of all the context features in the database. The new indices are given by the mapping
    new_indices. new_indices must include at least all the context features in the database.
    """
    new_index = case([(context_features.c.name == name, index) for (name, index) in new_indices.items()])
    await conn.execute(context_features.update().values(index=new_index))


async def db_get_context_features(conn: AsyncConnection) -> Sequence[Tuple[str, int]]:
    return (await conn.execute(
        select([context_features.c.name, context_features.c.index]).order_by(context_features.c.index),
    )).all()


async def db_get_not_found_context_features(conn: AsyncConnection, candidates: Iterable[str]) -> AbstractSet[str]:
    # todo improve? we expect both sets to be very small (<20 elements)
    return set(candidates) - set(name for (name, _) in await db_get_context_features(conn))


async def db_get_context_feature_index(conn: AsyncConnection, context_feature: str) -> Optional[int]:
    return (await conn.execute(select([context_features.c.index])
                               .where(context_features.c.name == context_feature))).scalar_one_or_none()


async def db_is_configurable_setting_from_context_features(conn: AsyncConnection, context_feature: str):
    setting_of_cf = (
        (await conn.execute(select([configurable.c.setting])
                            .where(configurable.c.context_feature == context_feature)))
        .scalar_one_or_none()
    )
    return setting_of_cf is not None


async def db_delete_context_feature(conn: AsyncConnection, context_feature: str):
    index_deleted = (await conn.execute(context_features.delete()
                                        .where(context_features.c.name == context_feature)
                                        .returning(context_features.c.index))).scalar_one_or_none()
    await conn.execute(context_features.update()
                       .where(context_features.c.index > index_deleted)
                       .values(index=context_features.c.index - 1))


async def db_move_after_context_feature(conn: AsyncConnection, index_to_move: int, target_index: int):
    """
    Changing context feature index to be after a different context feature.
    Example:
        {"a": 0, "b": 1, "c": 2}
        when called, move_after_context_feature(0, 1) will result {"b": 0, "a": 1, "c": 2}
    Args:
        conn: the transaction connection to use
        index_to_move: the index of the context feature to be moved after the target context feature.
        target_index: the index of the target to be second to the given context feature.
    """

    # first, change the index of the context feature to be moved to -1 so it won't be overridden
    await conn.execute(context_features.update()
                       .where(context_features.c.index == index_to_move)
                       .values(index=-1))
    if index_to_move < target_index:
        # move in between context features one step back
        await conn.execute(context_features.update()
                           .where(and_(context_features.c.index <= target_index,
                                       context_features.c.index > index_to_move))
                           .values(index=context_features.c.index - 1))
        # update the index of the context feature to be moved to its correct position
        await conn.execute(context_features.update()
                           .where(context_features.c.index == -1)
                           .values(index=target_index))
    else:
        # move in between context features one step forward
        await conn.execute(context_features.update()
                           .where(and_(context_features.c.index > target_index,
                                       context_features.c.index < index_to_move))
                           .values(index=context_features.c.index + 1))
        # update the index of the context feature to be moved to its correct position
        await conn.execute(context_features.update()
                           .where(context_features.c.index == -1)
                           .values(index=target_index + 1))


async def db_add_context_feature_to_end(conn: AsyncConnection, context_feature: str):
    last_index = (await conn.execute(
        select([func.max(context_features.c.index)]),
    )).scalar_one()
    await db_add_context_features(conn, {context_feature: last_index + 1})


async def db_add_context_features(conn: AsyncConnection, features: Mapping[str, int]):
    await conn.execute(context_features.insert().values(
        [{"name": context_feature, "index": index} for context_feature, index in features.items()])
    )
