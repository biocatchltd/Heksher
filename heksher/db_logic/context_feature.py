from logging import getLogger
from typing import AbstractSet, Iterable, Sequence

from sqlalchemy import and_, desc, select

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import configurable, context_features
from heksher.db_logic.util import supersequence_new_elements

logger = getLogger(__name__)


class ContextFeatureMixin(DBLogicBase):
    async def ensure_context_features(self, expected_context_features: Sequence[str]):
        """
        Ensure that the context features in the DB match those expected, or raise an error if that is not possible.
        Args:
            expected_context_features: The context features that should be present in the DB.
        Raises:
            raises a RuntimeError if the DB state cannot match the expected without deleting or reordering features.
        """
        query = select([context_features.c.name, context_features.c.index]).order_by(context_features.c.index)
        async with self.db_engine.connect() as conn:
            records = (await conn.execute(query)).mappings().all()
        expected = {cf: i for (i, cf) in enumerate(expected_context_features)}
        actual = {row['name']: row['index'] for row in records}
        super_sequence = supersequence_new_elements(expected_context_features, actual)
        if super_sequence is None:
            raise RuntimeError(f'expected context features to be a subsequence of {list(expected)}, '
                               f'actual: {list(actual)}')
        # get all context features that are out place with what we expect
        misplaced_keys = [k for k, v in actual.items() if expected[k] != v]
        if misplaced_keys:
            logger.warning('fixing indexing for context features', extra={'misplaced_keys': misplaced_keys})
            async with self.db_engine.begin() as conn:
                for k in misplaced_keys:
                    stmt = context_features.update().where(context_features.c.name == k).values(index=expected[k])
                    await conn.execute(stmt)
        if super_sequence:
            logger.info('adding new context features', extra={
                'new_context_features': [element for (element, _) in super_sequence]
            })
            async with self.db_engine.begin() as conn:
                await conn.execute(
                    context_features.insert().values(
                        [{'name': name, 'index': index} for (name, index) in super_sequence]
                    ))

    async def get_context_features(self) -> Sequence[str]:
        """
        Returns:
            A sequence of all the context features currently in the DB
        """
        async with self.db_engine.connect() as conn:
            rows = (await conn.execute(
                select([context_features.c.name]).order_by(context_features.c.index),
            )).scalars().all()
        return rows

    async def get_not_found_context_features(self, candidates: Iterable[str]) -> AbstractSet[str]:
        """
        Filter an iterable to only include strings that are not context features in the DB.
        Args:
            candidates: An iterable of potential context feature names

        Returns:
            A set including only the candidates that are not context features

        """
        # todo improve? we expect both sets to be very small (<20 elements)
        return set(candidates) - set(await self.get_context_features())

    async def get_context_feature_index(self, context_feature: str):
        """
        Args:
            context_feature: a potential context feature name.

        Returns:
            The index of the context feature name (if it exists in the DB, else None)
        """
        async with self.db_engine.connect() as conn:
            index = (await conn.execute(select([context_features.c.index])
                                        .where(context_features.c.name == context_feature))).scalar_one_or_none()
        return index

    async def is_configurable_setting_from_context_features(self, context_feature: str):
        async with self.db_engine.connect() as conn:
            setting_of_cf = (await conn.execute(select([configurable.c.setting])
                                                .where(configurable.c.context_feature == context_feature))) \
                .scalar_one_or_none()
            return setting_of_cf is not None

    async def delete_context_feature(self, context_feature: str):
        """
        Deletes the given context feature, and re-ordering the context features indexes
        Args:
            context_feature: a potential context feature name to be deleted.
        """
        async with self.db_engine.begin() as conn:
            index_deleted = (await conn.execute(context_features.delete()
                                                .where(context_features.c.name == context_feature)
                                                .returning(context_features.c.index))).scalar_one_or_none()
            await conn.execute(context_features.update()
                               .where(context_features.c.index > index_deleted)
                               .values(index=context_features.c.index - 1))

    async def move_after_context_feature(self, index_to_move: int, target_index: int):
        """
        Changing context feature index to be after a different context feature.
        Example:
            {"a": 0, "b": 1, "c": 2}
            when called, move_after_context_feature(0, 1) will result {"b": 0, "a": 1, "c": 2}
        Args:
            index_to_move: the index of the context feature to be moved after the target context feature.
            target_index: the index of the target to be second to the given context feature.
        """

        async with self.db_engine.begin() as conn:
            # first, change the index of the context feature to be moved to -2 so it won't be overridden
            await conn.execute(context_features.update()
                               .where(context_features.c.index == index_to_move)
                               .values(index=-2))
            if index_to_move < target_index:
                # move in between context features one step back
                await conn.execute(context_features.update()
                                   .where(and_(context_features.c.index <= target_index,
                                               context_features.c.index > index_to_move))
                                   .values(index=context_features.c.index - 1))
                # update the index of the context feature to be moved to its correct position
                await conn.execute(context_features.update()
                                   .where(context_features.c.index == -2)
                                   .values(index=target_index))
            else:
                # move in between context features one step forward
                await conn.execute(context_features.update()
                                   .where(and_(context_features.c.index > target_index,
                                               context_features.c.index < index_to_move))
                                   .values(index=context_features.c.index + 1))
                # update the index of the context feature to be moved to its correct position
                await conn.execute(context_features.update()
                                   .where(context_features.c.index == -2)
                                   .values(index=target_index+1))

    async def add_context_feature(self, context_feature: str) -> int:
        """
        Adds context feature to end of the context_features table.
        Args:
            context_feature: context_feature to be inserted.
        Returns: the index given to the new context feature.

        """
        async with self.db_engine.begin() as conn:
            last_index = (await conn.execute(
                select([context_features.c.index]).order_by(desc(context_features.c.index)).limit(1),
            )).scalar_one()
            await conn.execute(context_features.insert().values([{"name": context_feature, "index": last_index + 1}]))
        return last_index + 1
