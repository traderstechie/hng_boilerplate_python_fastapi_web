"""update user model from is_super_admin to is_superadmin

Revision ID: 3f455aaf9065
Revises: ff92a0037698
Create Date: 2024-08-10 03:45:26.585225

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f455aaf9065'
down_revision: Union[str, None] = 'ff92a0037698'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('is_superadmin', sa.Boolean(), server_default=sa.text('false'), nullable=True))
    op.drop_column('users', 'is_super_admin')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('is_super_admin', sa.BOOLEAN(), server_default=sa.text('false'), autoincrement=False, nullable=True))
    op.drop_column('users', 'is_superadmin')
    # ### end Alembic commands ###