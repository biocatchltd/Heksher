from typing import Sequence, Iterable, AbstractSet

from sqlalchemy import select, bindparam

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import context_features


class ContextFeatureMixin(DBLogicBase):
    async def ensure_context_features(self, expected_context_features: Sequence[str]):
        query = select([context_features.c.name, context_features.c.index]).order_by(context_features.c.index)
        records = await self.db.fetch_all(query)
        if not records:
            query = context_features.insert()
            values = [{'name': cf, 'index': i} for (i, cf) in enumerate(expected_context_features)]
            await self.db.execute_many(query, values)
            return
        expected = {cf: i for (i, cf) in enumerate(expected_context_features)}
        actual = {row['name']: row['index'] for row in records}
        if list(actual) != list(expected):
            raise RuntimeError(f'expected context features: {list(expected)}, actual: {list(actual)}')
        bad_keys = [k for k, v in expected.items() if actual[k] != v]
        self.logger.warning('fixing indexing for context features', extra={'bad_keys': bad_keys})
        index_fix = [{'k': k, 'v': expected[k]} for k in bad_keys]
        query = (context_features
                 .update()
                 .where(context_features.c.name == bindparam('k'))
                 .values(index=bindparam('v'))
                 )
        await self.db.execute_many(query, index_fix)

    async def get_context_features(self) -> Sequence[str]:
        rows = await self.db.fetch_all(
            select([context_features.c.name]).order_by(context_features.c.index),
        )
        return [row['name'] for row in rows]

    async def get_not_context_features(self, candidates: Iterable[str]) -> AbstractSet[str]:
        return set(candidates) - set(await self.get_context_features())

    async def is_context_feature(self, context_feature: str):
        rows = await self.db.fetch_one(select([context_features.c.name])
                                       .where(context_features.c.name==context_feature))
        return rows is not None
