from sqlalchemy.ext.asyncio import AsyncEngine


class DBLogicBase:
    """
    A base class for DBLogic mixins
    """
    db_engine: AsyncEngine
