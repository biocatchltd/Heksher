from logging import Logger
from databases import Database


class DBLogicBase:
    """
    A base class for DBLogic mixins
    """
    db: Database
    logger: Logger
