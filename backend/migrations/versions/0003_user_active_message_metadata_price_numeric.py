"""Add active users, message metadata, and exact decimal price storage."""

from alembic import op
import sqlalchemy as sa

revision = "0003_user_active_price_numeric"
down_revision = "0002_user_full_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("is_active", server_default=None)

    op.add_column("messages", sa.Column("metadata", sa.JSON(), nullable=True))
    with op.batch_alter_table("predictions") as batch_op:
        batch_op.alter_column(
            "predicted_price",
            existing_type=sa.Float(),
            type_=sa.Numeric(16, 2),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("predictions") as batch_op:
        batch_op.alter_column(
            "predicted_price",
            existing_type=sa.Numeric(16, 2),
            type_=sa.Float(),
            existing_nullable=False,
        )
    op.drop_column("messages", "metadata")
    op.drop_column("users", "is_active")
