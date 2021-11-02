""""Added alias table"

Revision ID: 3b7bd626fabd
Revises: 89eab5c8510a
Create Date: 2021-11-01 15:36:18.522890

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b7bd626fabd'
down_revision = '89eab5c8510a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('setting_aliases',
    sa.Column('setting', sa.String(), nullable=True),
    sa.Column('alias', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['setting'], ['settings.name'], onupdate='CASCADE', ondelete='CASCADE')
    )
    op.create_index(op.f('ix_setting_aliases_alias'), 'setting_aliases', ['alias'], unique=True)
    op.create_index(op.f('ix_setting_aliases_setting'), 'setting_aliases', ['setting'], unique=False)
    op.drop_constraint('conditions_rule_fkey', 'conditions', type_='foreignkey')
    op.create_foreign_key(None, 'conditions', 'rules', ['rule'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_constraint('configurable_setting_fkey', 'configurable', type_='foreignkey')
    op.create_foreign_key(None, 'configurable', 'settings', ['setting'], ['name'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_constraint('rule_metadata_rule_fkey', 'rule_metadata', type_='foreignkey')
    op.create_foreign_key(None, 'rule_metadata', 'rules', ['rule'], ['id'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_constraint('rules_setting_fkey', 'rules', type_='foreignkey')
    op.create_foreign_key(None, 'rules', 'settings', ['setting'], ['name'], onupdate='CASCADE', ondelete='CASCADE')
    op.drop_constraint('setting_metadata_setting_fkey', 'setting_metadata', type_='foreignkey')
    op.create_foreign_key(None, 'setting_metadata', 'settings', ['setting'], ['name'], onupdate='CASCADE', ondelete='CASCADE')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'setting_metadata', type_='foreignkey')
    op.create_foreign_key('setting_metadata_setting_fkey', 'setting_metadata', 'settings', ['setting'], ['name'], ondelete='CASCADE')
    op.drop_constraint(None, 'rules', type_='foreignkey')
    op.create_foreign_key('rules_setting_fkey', 'rules', 'settings', ['setting'], ['name'], ondelete='CASCADE')
    op.drop_constraint(None, 'rule_metadata', type_='foreignkey')
    op.create_foreign_key('rule_metadata_rule_fkey', 'rule_metadata', 'rules', ['rule'], ['id'], ondelete='CASCADE')
    op.drop_constraint(None, 'configurable', type_='foreignkey')
    op.create_foreign_key('configurable_setting_fkey', 'configurable', 'settings', ['setting'], ['name'], ondelete='CASCADE')
    op.drop_constraint(None, 'conditions', type_='foreignkey')
    op.create_foreign_key('conditions_rule_fkey', 'conditions', 'rules', ['rule'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_setting_aliases_setting'), table_name='setting_aliases')
    op.drop_index(op.f('ix_setting_aliases_alias'), table_name='setting_aliases')
    op.drop_table('setting_aliases')
    # ### end Alembic commands ###
