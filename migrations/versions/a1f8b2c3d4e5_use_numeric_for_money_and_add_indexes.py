"""use_numeric_for_money_and_add_indexes

Revision ID: a1f8b2c3d4e5
Revises: 887c43f6a559
Create Date: 2026-10-03 01:57:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f8b2c3d4e5"
down_revision: Union[str, None] = "887c43f6a559"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Изменение типа amount в transactions на Numeric(12, 2)
    op.alter_column(
        "transactions",
        "amount",
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
    )

    # 2. Добавление составных индексов в transactions
    op.create_index(
        "ix_transactions_user_id_date",
        "transactions",
        ["user_id", "date"],
        unique=False,
    )
    op.create_index(
        "ix_transactions_user_id_created_at",
        "transactions",
        ["user_id", "created_at"],
        unique=False,
    )

    # 3. Изменение типа limit_amount в budgets на Numeric(12, 2)
    op.alter_column(
        "budgets",
        "limit_amount",
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=12, scale=2),
        existing_nullable=False,
    )

    # 4. Добавление составного уникального ограничения на бюджеты
    op.create_unique_constraint(
        "uq_budget_user_cat_period",
        "budgets",
        ["user_id", "category", "month", "year"],
    )


def downgrade() -> None:
    # 4. Удаление уникального ограничения на бюджеты
    op.drop_constraint("uq_budget_user_cat_period", "budgets", type_="unique")

    # 3. Возврат типа limit_amount в budgets к Float
    op.alter_column(
        "budgets",
        "limit_amount",
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Float(),
        existing_nullable=False,
    )

    # 2. Удаление индексов transactions
    op.drop_index("ix_transactions_user_id_created_at", table_name="transactions")
    op.drop_index("ix_transactions_user_id_date", table_name="transactions")

    # 1. Возврат типа amount в transactions к Float
    op.alter_column(
        "transactions",
        "amount",
        existing_type=sa.Numeric(precision=12, scale=2),
        type_=sa.Float(),
        existing_nullable=False,
    )
