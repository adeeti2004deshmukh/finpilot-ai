"""Phase 4.5 accounts, revocable sessions and onboarding; preserve existing owners."""
from alembic import op
import sqlalchemy as sa

revision = "c45_auth_onboarding"
down_revision = "bf8c5f1a4a74"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("normalized_email", sa.String(254), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
        batch.add_column(sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.alter_column("age", existing_type=sa.Integer(), nullable=True)
    op.execute("UPDATE users SET normalized_email = lower(trim(email))")
    op.create_index("ix_users_normalized_email", "users", ["normalized_email"], unique=True)
    op.execute("UPDATE users SET is_demo = true, onboarding_completed = true WHERE normalized_email = 'aarav.sharma.demo@example.com'")
    with op.batch_alter_table("financial_profiles") as batch:
        batch.add_column(sa.Column("typical_essential_expenses", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.drop_constraint("ck_profile_emergency_months", type_="check")
        batch.create_check_constraint("ck_profile_emergency_months", "emergency_fund_target_months BETWEEN 1 AND 24")
    # Keep shared default rules; all new rules can have a private owner.
    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    unique_name = "merchant_rules_merchant_pattern_key"
    if not op.get_context().as_sql:
        constraints = sa.inspect(op.get_bind()).get_unique_constraints("merchant_rules")
        unique_name = next((c["name"] or "uq_merchant_rules_merchant_pattern" for c in constraints
                            if c["column_names"] == ["merchant_pattern"]), unique_name)
    with op.batch_alter_table("merchant_rules", naming_convention=naming) as batch:
        batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_merchant_rules_owner", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch.drop_constraint(unique_name, type_="unique")
        batch.create_unique_constraint("uq_rule_owner_pattern", ["user_id", "merchant_pattern"])
        batch.create_index("ix_merchant_rules_user_id", ["user_id"])
    op.create_table("auth_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_table("auth_throttles", sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("window_started", sa.DateTime(timezone=True), nullable=False))


def downgrade():
    # A fresh-schema roundtrip is supported; refuse to discard registered accounts
    # or private rules, or to coerce custom emergency targets in a populated DB.
    if not op.get_context().as_sql:
        bind = op.get_bind()
        if bind.scalar(sa.text("SELECT count(*) FROM users WHERE password_hash IS NOT NULL")) or bind.scalar(sa.text("SELECT count(*) FROM merchant_rules WHERE user_id IS NOT NULL")) or bind.scalar(sa.text("SELECT count(*) FROM financial_profiles WHERE emergency_fund_target_months NOT IN (3,6,9,12)")):
            raise RuntimeError("Rollback would discard account data; restore a verified backup instead")
    op.drop_table("auth_throttles")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("merchant_rules") as batch:
        batch.drop_index("ix_merchant_rules_user_id")
        batch.drop_constraint("uq_rule_owner_pattern", type_="unique")
        batch.drop_constraint("fk_merchant_rules_owner", type_="foreignkey")
        batch.drop_column("user_id")
        batch.create_unique_constraint("merchant_rules_merchant_pattern_key", ["merchant_pattern"])
    with op.batch_alter_table("financial_profiles") as batch:
        batch.drop_column("typical_essential_expenses")
        batch.drop_constraint("ck_profile_emergency_months", type_="check")
        batch.create_check_constraint("ck_profile_emergency_months", "emergency_fund_target_months IN (3,6,9,12)")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_normalized_email")
        for column in ("normalized_email", "password_hash", "onboarding_completed", "is_demo"):
            batch.drop_column(column)
        batch.alter_column("age", existing_type=sa.Integer(), nullable=False)
