"""Rename token to token_hash in Token model

Revision ID: a32f40d3601a
Revises: a1f8b2c3d4e5
Create Date: 2026-10-03 13:15:37.594569

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a32f40d3601a"
down_revision: Union[str, None] = "a1f8b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Очищаем таблицу токенов, так как старые токены не хэшированы и станут невалидными
    op.execute("DELETE FROM tokens")

    # Переименовываем колонку
    op.alter_column("tokens", "token", new_column_name="token_hash")
    op.drop_constraint("uq_tokens_token", "tokens", type_="unique")
    op.create_unique_constraint("uq_tokens_token_hash", "tokens", ["token_hash"])


def downgrade() -> None:
    op.alter_column("tokens", "token_hash", new_column_name="token")
    op.drop_constraint("uq_tokens_token_hash", "tokens", type_="unique")
    op.create_unique_constraint("uq_tokens_token", "tokens", ["token"])
