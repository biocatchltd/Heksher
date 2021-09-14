from logging import getLogger
from typing import AbstractSet, Iterable, Sequence

from sqlalchemy import select

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import context_features
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

    async def is_context_feature(self, context_feature: str):
        """
        Args:
            context_feature: a potential context feature name.

        Returns:
            Whether the string is a context feature name in the DB
        """
        async with self.db_engine.connect() as conn:
            rows = (await conn.execute(select([context_features.c.name])
                                       .where(context_features.c.name == context_feature))).scalar_one_or_none()
        return rows is not None
