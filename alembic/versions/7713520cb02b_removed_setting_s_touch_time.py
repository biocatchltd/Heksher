""""removed setting's touch time"

Revision ID: 7713520cb02b
Revises: 37b28f79cccf
Create Date: 2021-12-26 14:07:09.427397

"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = '7713520cb02b'
down_revision = '37b28f79cccf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('settings', 'last_touch_time')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('settings', sa.Column('last_touch_time', postgresql.TIMESTAMP(), autoincrement=False, nullable=False,
                                        server_default=sa.func.now()))
    # ### end Alembic commands ###
