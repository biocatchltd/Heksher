from sqlalchemy import TIMESTAMP, Column, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

settings = Table('settings', metadata,
                 Column('name', String, primary_key=True),
                 Column('type', String, nullable=False),
                 Column('default_value', String, nullable=True),
                 Column('last_touch_time', TIMESTAMP(), nullable=False),
                 )

context_features = Table('context_features', metadata,
                         Column('name', String, primary_key=True),
                         Column('index', Integer, unique=True),
                         )

configurable = Table('configurable', metadata,
                     Column('setting', ForeignKey(settings.columns.name, ondelete="CASCADE"), index=True),
                     Column('context_feature', ForeignKey(context_features.columns.name)),
                     UniqueConstraint('setting', 'context_feature')
                     )

rules = Table('rules', metadata,
              Column('id', Integer, primary_key=True, autoincrement=True),
              Column('setting', ForeignKey(settings.columns.name, ondelete="CASCADE"), index=True),
              Column('value', String, nullable=False),
              )

conditions = Table('conditions', metadata,
                   Column('rule', ForeignKey(rules.columns.id, ondelete="CASCADE"), index=True),
                   Column('context_feature', ForeignKey(context_features.columns.name)),
                   Column('feature_value', String, nullable=False),
                   UniqueConstraint('rule', 'context_feature'),
                   )

setting_metadata = Table('setting_metadata', metadata,
                         Column('setting', ForeignKey(settings.columns.name, ondelete="CASCADE"), index=True),
                         Column('key', String, nullable=False),
                         Column('value', JSONB, nullable=False),
                         UniqueConstraint('setting', 'key'),
                         )

rule_metadata = Table('rule_metadata', metadata,
                      Column('rule', ForeignKey(rules.columns.id, ondelete="CASCADE"), index=True),
                      Column('key', String, nullable=False),
                      Column('value', JSONB, nullable=False),
                      UniqueConstraint('rule', 'key'),
                      )
