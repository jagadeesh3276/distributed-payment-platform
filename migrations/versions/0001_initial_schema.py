from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("accounts",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("account_number",sa.String(32),nullable=False,unique=True),
        sa.Column("owner_id",sa.String(64),nullable=False),
        sa.Column("currency",sa.String(3),nullable=False,server_default="INR"),
        sa.Column("balance",sa.Numeric(18,2),nullable=False,server_default="0.00"),
        sa.Column("status",sa.String(20),nullable=False,server_default="active"),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'",name="ck_accounts_currency_format"),
        sa.CheckConstraint("balance >= 0",name="ck_accounts_balance_nonnegative"))
    op.create_index("ix_accounts_owner_id","accounts",["owner_id"])
    op.create_table("transfers",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("reference",sa.String(36),nullable=False,unique=True),
        sa.Column("source_account",sa.String(32),nullable=False),sa.Column("destination_account",sa.String(32),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("currency",sa.String(3),nullable=False),
        sa.Column("status",sa.String(20),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_transfers_reference","transfers",["reference"])
    op.create_index("ix_transfers_source_account","transfers",["source_account"])
    op.create_index("ix_transfers_destination_account","transfers",["destination_account"])
    op.create_table("ledger_entries",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("transfer_reference",sa.String(36),nullable=False),
        sa.Column("account_number",sa.String(32),nullable=False),sa.Column("direction",sa.String(10),nullable=False),
        sa.Column("amount",sa.Numeric(18,2),nullable=False),sa.Column("currency",sa.String(3),nullable=False),
        sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_ledger_entries_transfer_reference","ledger_entries",["transfer_reference"])
    op.create_index("ix_ledger_entries_account_number","ledger_entries",["account_number"])
    op.create_table("idempotency_records",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("key",sa.String(128),nullable=False,unique=True),
        sa.Column("request_hash",sa.String(64),nullable=False),sa.Column("response_status",sa.Integer(),nullable=False),
        sa.Column("response_body",postgresql.JSONB(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_table("outbox_events",
        sa.Column("id",sa.Integer(),primary_key=True),sa.Column("event_type",sa.String(100),nullable=False),
        sa.Column("aggregate_id",sa.String(100),nullable=False),sa.Column("payload",postgresql.JSONB(),nullable=False),
        sa.Column("published_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_outbox_events_aggregate_id","outbox_events",["aggregate_id"])
def downgrade():
    op.drop_table("outbox_events"); op.drop_table("idempotency_records"); op.drop_table("ledger_entries"); op.drop_table("transfers"); op.drop_table("accounts")
