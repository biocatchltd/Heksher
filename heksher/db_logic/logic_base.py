from logging import Logger
from databases import Database


class DBLogicBase:
    db : Database
    logger: Logger
