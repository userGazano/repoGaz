from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("referral_code", sa.String(32), nullable=False),
        sa.Column("referred_by_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.id"]),
        sa.UniqueConstraint("telegram_id"), sa.UniqueConstraint("referral_code"))

    op.create_table("products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("price_stars", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))

    op.create_table("accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("country", sa.String(100), nullable=False),
        sa.Column("public_label", sa.String(255), nullable=False),
        sa.Column("encrypted_payload", sa.Text()),
        sa.Column("status", sa.String(32), server_default="available", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("sold_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]))

    op.create_table("orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("amount_stars", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("telegram_charge_id", sa.String(255), unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]))

    op.create_table("purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("delivered_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]))

    op.create_table("referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.Integer(), nullable=False),
        sa.Column("referred_user_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["referred_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]))

    op.create_table("audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_telegram_id", sa.BigInteger()),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(100)),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))

    op.create_table("idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()))

def downgrade():
    for t in ["idempotency_keys","audit_logs","referral_rewards","purchases","orders","accounts","products","users"]:
        op.drop_table(t)
