"""Store the user's display name."""

from alembic import op
import sqlalchemy as sa

revision = "0002_user_full_name"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=200), nullable=False, server_default=""),
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("full_name", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "full_name")
