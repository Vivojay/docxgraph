"""enterprise alignment

Revision ID: 0002_enterprise_alignment
Revises: 0001_initial
Create Date: 2026-05-02 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "0002_enterprise_alignment"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("export_format", sa.String(length=20), nullable=False, server_default="json"),
        sa.Column("feature_flags_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.UniqueConstraint("org_id", name="uq_organization_settings_org_id"),
    )
    op.create_index("ix_organization_settings_id", "organization_settings", ["id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])

    op.create_table(
        "case_similarity_edges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("similar_case_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("vector_sim", sa.Float(), nullable=False, server_default="0"),
        sa.Column("tag_sim", sa.Float(), nullable=False, server_default="0"),
        sa.Column("constraint_sim", sa.Float(), nullable=False, server_default="0"),
        sa.Column("explanation_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["similar_case_id"], ["cases.id"]),
        sa.UniqueConstraint("case_id", "similar_case_id", name="uq_case_similarity_edge"),
    )
    op.create_index("ix_case_similarity_edges_id", "case_similarity_edges", ["id"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("role", existing_type=sa.String(length=20), type_=sa.String(length=20))

    with op.batch_alter_table("doctor_profiles") as batch_op:
        batch_op.add_column(sa.Column("proof_status", sa.String(length=50), nullable=True, server_default="manual_review"))

    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("specialty_domain", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("age_bucket", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("resource_setting", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("follow_up", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("record_schema", sa.String(length=100), nullable=False, server_default="clinical_micro_case"))

    with op.batch_alter_table("case_revisions") as batch_op:
        batch_op.add_column(sa.Column("diff_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("case_revisions") as batch_op:
        batch_op.drop_column("diff_json")

    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("record_schema")
        batch_op.drop_column("follow_up")
        batch_op.drop_column("resource_setting")
        batch_op.drop_column("age_bucket")
        batch_op.drop_column("specialty_domain")

    with op.batch_alter_table("doctor_profiles") as batch_op:
        batch_op.drop_column("proof_status")

    op.drop_index("ix_case_similarity_edges_id", table_name="case_similarity_edges")
    op.drop_table("case_similarity_edges")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_organization_settings_id", table_name="organization_settings")
    op.drop_table("organization_settings")
