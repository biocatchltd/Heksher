from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

settings = Table('settings', metadata,
                 Column('name', String, primary_key=True),
                 Column('type', String, nullable=False),
                 Column('default_value', String, nullable=False),
                 Column('version', String, nullable=False),
                 )

context_features = Table('context_features', metadata,
                         Column('name', String, primary_key=True),
                         Column('index', Integer, unique=True),
                         )

configurable = Table('configurable', metadata,
                     Column('setting', ForeignKey(settings.columns.name,
                                                  ondelete="CASCADE", onupdate="CASCADE"), index=True, nullable=False),
                     Column('context_feature', ForeignKey(context_features.columns.name), nullable=False),
                     UniqueConstraint('setting', 'context_feature')
                     )

rules = Table('rules', metadata,
              Column('id', Integer, primary_key=True, autoincrement=True),
              Column('setting', ForeignKey(settings.columns.name, ondelete="CASCADE", onupdate="CASCADE"), index=True,
                     nullable=False),
              Column('value', String, nullable=False),
              )

conditions = Table('conditions', metadata,
                   Column('rule', ForeignKey(rules.columns.id, ondelete="CASCADE", onupdate="CASCADE"), index=True,
                          nullable=False),
                   Column('context_feature', ForeignKey(context_features.columns.name), nullable=False),
                   Column('feature_value', String, nullable=False),
                   UniqueConstraint('rule', 'context_feature'),
                   )

setting_metadata = Table('setting_metadata', metadata,
                         Column('setting', ForeignKey(settings.columns.name,
                                                      ondelete="CASCADE", onupdate="CASCADE"), index=True,
                                nullable=False),
                         Column('key', String, nullable=False),
                         Column('value', JSONB, nullable=False),
                         UniqueConstraint('setting', 'key'),
                         )

rule_metadata = Table('rule_metadata', metadata,
                      Column('rule', ForeignKey(rules.columns.id, ondelete="CASCADE", onupdate="CASCADE"), index=True,
                             nullable=False),
                      Column('key', String, nullable=False),
                      Column('value', JSONB, nullable=False),
                      UniqueConstraint('rule', 'key'),
                      )

setting_aliases = Table('setting_aliases', metadata,
                        Column('setting', ForeignKey(settings.columns.name,
                                                     ondelete="CASCADE", onupdate="CASCADE"), index=True,
                               nullable=False),
                        Column('alias', String, primary_key=True),
                        )
