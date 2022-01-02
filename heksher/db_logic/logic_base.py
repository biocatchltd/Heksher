from sqlalchemy.ext.asyncio import AsyncEngine


class DBLogicBase:
    """
    A base class for DBLogic mixins
    """
    db_engine: AsyncEngine

    async def bump_setting_version(self, conn, setting_name: str, new_version: str) -> None:
        pass
