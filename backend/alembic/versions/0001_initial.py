"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    role_enum = sa.Enum("doctor", "admin", name="roleenum")
    tag_type_enum = sa.Enum("specialty", "free", name="tagtypeenum")
    availability_enum = sa.Enum("available", "busy", "offline", name="availabilityenum")

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"])
    op.create_index("ix_organizations_name", "organizations", ["name"], unique=True)

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_teams_id", "teams", ["id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"]),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "doctor_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("specialty", sa.String(length=200), nullable=False),
        sa.Column("years_experience", sa.Integer(), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=True),
        sa.Column("availability_status", availability_enum, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", name="uq_doctor_profiles_user_id"),
    )
    op.create_index("ix_doctor_profiles_id", "doctor_profiles", ["id"])

    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("case_type", sa.String(length=50), nullable=False, server_default="general"),
        sa.Column("specialty", sa.String(length=200), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=False),
        sa.Column("demographics", sa.Text(), nullable=True),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("suspected_dx", sa.Text(), nullable=True),
        sa.Column("final_dx", sa.Text(), nullable=True),
        sa.Column("interventions", sa.Text(), nullable=True),
        sa.Column("outcomes", sa.Text(), nullable=True),
        sa.Column("what_changed", sa.Text(), nullable=True),
        sa.Column("template_fields", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
    )
    op.create_index("ix_cases_id", "cases", ["id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tag_type", tag_type_enum, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tags_id", "tags", ["id"])
    op.create_index("ix_tags_name", "tags", ["name"])

    op.create_table(
        "case_tags",
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]),
        sa.PrimaryKeyConstraint("case_id", "tag_id"),
    )

    op.create_table(
        "case_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("editor_id", sa.Integer(), nullable=False),
        sa.Column("revision_num", sa.Integer(), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["editor_id"], ["users.id"]),
    )
    op.create_index("ix_case_revisions_id", "case_revisions", ["id"])

    op.create_table(
        "case_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("vector", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.UniqueConstraint("case_id", "provider", name="uq_case_embedding"),
    )
    op.create_index("ix_case_embeddings_id", "case_embeddings", ["id"])

    op.create_table(
        "endorsements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("doctor_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["doctor_id"], ["users.id"]),
        sa.UniqueConstraint("case_id", "doctor_id", name="uq_endorsement"),
    )
    op.create_index("ix_endorsements_id", "endorsements", ["id"])

    op.create_table(
        "case_view_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_index("ix_case_view_logs_id", "case_view_logs", ["id"])

    op.create_table(
        "auth_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_auth_events_id", "auth_events", ["id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_hash"),
    )
    op.create_index("ix_refresh_tokens_id", "refresh_tokens", ["id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_auth_events_id", table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_index("ix_case_view_logs_id", table_name="case_view_logs")
    op.drop_table("case_view_logs")
    op.drop_index("ix_endorsements_id", table_name="endorsements")
    op.drop_table("endorsements")
    op.drop_index("ix_case_embeddings_id", table_name="case_embeddings")
    op.drop_table("case_embeddings")
    op.drop_index("ix_case_revisions_id", table_name="case_revisions")
    op.drop_table("case_revisions")
    op.drop_table("case_tags")
    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_index("ix_tags_id", table_name="tags")
    op.drop_table("tags")
    op.drop_index("ix_cases_id", table_name="cases")
    op.drop_table("cases")
    op.drop_index("ix_doctor_profiles_id", table_name="doctor_profiles")
    op.drop_table("doctor_profiles")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_teams_id", table_name="teams")
    op.drop_table("teams")
    op.drop_index("ix_organizations_name", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")
    role_enum = sa.Enum("doctor", "admin", name="roleenum")
    tag_type_enum = sa.Enum("specialty", "free", name="tagtypeenum")
    availability_enum = sa.Enum("available", "busy", "offline", name="availabilityenum")
    role_enum.drop(op.get_bind(), checkfirst=True)
    tag_type_enum.drop(op.get_bind(), checkfirst=True)
    availability_enum.drop(op.get_bind(), checkfirst=True)
