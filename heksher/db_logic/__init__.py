from sqlalchemy.ext.asyncio import AsyncEngine

from heksher.db_logic.context_feature import ContextFeatureMixin
from heksher.db_logic.rule import RuleMixin
from heksher.db_logic.rule_metadata import RuleMetadataMixin
from heksher.db_logic.setting import SettingMixin
from heksher.db_logic.setting_metadata import SettingMetadataMixin


class DBLogic(ContextFeatureMixin, SettingMixin, RuleMixin, SettingMetadataMixin, RuleMetadataMixin):
    """
    Class to handle all logic for interacting with the DB
    """
    # note that all methods are implemented inside mixin classes
    def __init__(self, engine: AsyncEngine):
        self.db_engine = engine
