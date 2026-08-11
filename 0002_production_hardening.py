from alembic import op
import sqlalchemy as sa

revision = "0002_production_hardening"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("accounts", sa.Column("reserved_at", sa.DateTime(), nullable=True))
    op.add_column("accounts", sa.Column("notes", sa.Text(), nullable=False, server_default=""))
    op.add_column("orders", sa.Column("account_id", sa.Integer(), nullable=True))
    op.add_column("orders", sa.Column("telegram_payment_id", sa.String(255), nullable=True))
    op.create_index("ix_orders_account_id", "orders", ["account_id"])
    op.create_unique_constraint("uq_orders_telegram_payment_id", "orders", ["telegram_payment_id"])
    op.create_foreign_key("fk_orders_account_id", "orders", "accounts", ["account_id"], ["id"])
    op.create_index("ix_accounts_product_status", "accounts", ["product_id", "status"])

def downgrade():
    op.drop_index("ix_accounts_product_status", table_name="accounts")
    op.drop_constraint("fk_orders_account_id", "orders", type_="foreignkey")
    op.drop_constraint("uq_orders_telegram_payment_id", "orders", type_="unique")
    op.drop_index("ix_orders_account_id", table_name="orders")
    op.drop_column("orders", "telegram_payment_id")
    op.drop_column("orders", "account_id")
    op.drop_column("accounts", "notes")
    op.drop_column("accounts", "reserved_at")
