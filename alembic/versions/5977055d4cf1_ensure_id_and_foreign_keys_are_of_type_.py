"""Ensure id and foreign keys are of type String

Revision ID: 5977055d4cf1
Revises: 1fc08cda8f3b
Create Date: 2024-08-07 22:16:02.064783

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5977055d4cf1'
down_revision: Union[str, None] = '1fc08cda8f3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###