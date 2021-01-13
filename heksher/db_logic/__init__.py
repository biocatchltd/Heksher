from logging import Logger

from databases import Database

from heksher.db_logic.context_feature import ContextFeatureMixin
from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.rule import RuleMixin
from heksher.db_logic.setting import SettingMixin


class DBLogic(ContextFeatureMixin, SettingMixin, RuleMixin):
    """
    Class to handle all logic for interacting with the DB
    """
    # note that all methods are implemented inside mixin classes
    def __init__(self, logger: Logger, db: Database):
        self.db = db
        self.logger = logger
