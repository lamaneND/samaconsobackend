"""add refresh token fields to user_session

Revision ID: refresh_token_user_session
Revises: 6f541bba54f8
Create Date: 2025-01-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'refresh_token_user_session'
down_revision: Union[str, None] = '6f541bba54f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add refresh_token_hash and refresh_token_expires_at to user_session."""
    # Ajouter refresh_token_hash (String nullable)
    op.add_column('user_session', sa.Column('refresh_token_hash', sa.String(), nullable=True))
    
    # Ajouter refresh_token_expires_at (DateTime timezone nullable)
    op.add_column('user_session', sa.Column('refresh_token_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema - Remove refresh_token fields from user_session."""
    op.drop_column('user_session', 'refresh_token_expires_at')
    op.drop_column('user_session', 'refresh_token_hash')

