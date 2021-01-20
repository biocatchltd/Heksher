from logging import getLogger
from typing import Sequence, Iterable, AbstractSet

from sqlalchemy import select

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import context_features
from heksher.db_logic.util import is_supersequence

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
        records = await self.db.fetch_all(query)
        expected = {cf: i for (i, cf) in enumerate(expected_context_features)}
        actual = {row['name']: row['index'] for row in records}
        super_sequence = is_supersequence(expected_context_features, actual)
        if not super_sequence:
            raise RuntimeError(f'expected context features to be a subsequence of {list(expected)}, '
                               f'actual: {list(actual)}')
        # get all context features that are out place with what we expect
        misplaced_keys = [k for k, v in actual.items() if expected[k] != v]
        if misplaced_keys:
            logger.warning('fixing indexing for context features', extra={'misplaced_keys': misplaced_keys})
            query = """
            UPDATE context_features
            SET index = :v
            WHERE name = :k
            """
            await self.db.execute_many(query, [{'k': k, 'v': expected[k]} for k in misplaced_keys])
        if super_sequence.new_elements:
            logger.info('adding new context features', extra={
                'new_context_features': [element for (element, _) in super_sequence.new_elements]
            })
            await self.db.execute_many(
                context_features.insert(),
                [{'name': name, 'index': index} for (name, index) in super_sequence.new_elements]
            )

    async def get_context_features(self) -> Sequence[str]:
        """
        Returns:
            A sequence of all the context features currently in the DB
        """
        rows = await self.db.fetch_all(
            select([context_features.c.name]).order_by(context_features.c.index),
        )
        return [row['name'] for row in rows]

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
        rows = await self.db.fetch_one(select([context_features.c.name])
                                       .where(context_features.c.name == context_feature))
        return rows is not None
