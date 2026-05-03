from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


class RoleEnum(str, Enum):
    clinician = "clinician"
    org_admin = "org_admin"
    reviewer = "reviewer"
    auditor = "auditor"
    super_admin = "super_admin"
    doctor = "clinician"
    admin = "org_admin"


class TagTypeEnum(str, Enum):
    specialty = "specialty"
    free = "free"
    outcome = "outcome"
    intervention = "intervention"


class AvailabilityEnum(str, Enum):
    available = "available"
    busy = "busy"
    offline = "offline"


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)
    region = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    teams = relationship("Team", back_populates="organization")
    settings = relationship("OrganizationSettings", back_populates="organization", uselist=False)


class OrganizationSettings(Base):
    __tablename__ = "organization_settings"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), unique=True, nullable=False)
    retention_days = Column(Integer, nullable=False, default=365)
    export_format = Column(String(20), nullable=False, default="json")
    feature_flags_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="settings")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    name = Column(String(200), nullable=False)

    organization = relationship("Organization", back_populates="teams")
    users = relationship("User", back_populates="team")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SqlEnum(RoleEnum), default=RoleEnum.clinician, nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    organization = relationship("Organization", back_populates="users")
    team = relationship("Team", back_populates="users")
    profile = relationship("DoctorProfile", back_populates="user", uselist=False)
    cases = relationship("Case", back_populates="author")


class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    specialty = Column(String(200), nullable=False)
    years_experience = Column(Integer, nullable=True)
    region = Column(String(100), nullable=True)
    verified = Column(Boolean, default=False)
    availability_status = Column(SqlEnum(AvailabilityEnum), default=AvailabilityEnum.available)
    proof_status = Column(String(50), nullable=True, default="manual_review")

    user = relationship("User", back_populates="profile")


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    case_type = Column(String(50), nullable=False, default="general")
    specialty = Column(String(200), nullable=False)
    specialty_domain = Column(String(200), nullable=True)
    symptoms = Column(Text, nullable=False)
    demographics = Column(Text, nullable=True)
    age_bucket = Column(String(50), nullable=True)
    constraints = Column(Text, nullable=True)
    resource_setting = Column(String(120), nullable=True)
    suspected_dx = Column(Text, nullable=True)
    final_dx = Column(Text, nullable=True)
    interventions = Column(Text, nullable=True)
    outcomes = Column(Text, nullable=True)
    follow_up = Column(Text, nullable=True)
    what_changed = Column(Text, nullable=True)
    template_fields = Column(Text, nullable=True)
    record_schema = Column(String(100), nullable=False, default="clinical_micro_case")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    author = relationship("User", back_populates="cases")
    tags = relationship("CaseTag", back_populates="case")
    revisions = relationship("CaseRevision", back_populates="case")
    embeddings = relationship("CaseEmbedding", back_populates="case")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), index=True, nullable=False)
    tag_type = Column(SqlEnum(TagTypeEnum), default=TagTypeEnum.free)
    created_at = Column(DateTime, default=datetime.utcnow)


class CaseTag(Base):
    __tablename__ = "case_tags"

    case_id = Column(Integer, ForeignKey("cases.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)

    case = relationship("Case", back_populates="tags")
    tag = relationship("Tag")


class CaseRevision(Base):
    __tablename__ = "case_revisions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    editor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    revision_num = Column(Integer, nullable=False)
    data_json = Column(Text, nullable=False)
    diff_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    case = relationship("Case", back_populates="revisions")


class CaseEmbedding(Base):
    __tablename__ = "case_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    provider = Column(String(50), nullable=False)
    vector = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="embeddings")
    __table_args__ = (UniqueConstraint("case_id", "provider", name="uq_case_embedding"),)


class CaseSimilarityEdge(Base):
    __tablename__ = "case_similarity_edges"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    similar_case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    score = Column(Float, nullable=False)
    vector_sim = Column(Float, nullable=False, default=0.0)
    tag_sim = Column(Float, nullable=False, default=0.0)
    constraint_sim = Column(Float, nullable=False, default=0.0)
    explanation_json = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "similar_case_id", name="uq_case_similarity_edge"),
    )


class Endorsement(Base):
    __tablename__ = "endorsements"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("case_id", "doctor_id", name="uq_endorsement"),)


class CaseViewLog(Base):
    __tablename__ = "case_view_logs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(300), nullable=True)
    viewed_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(300), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuthEvent(Base):
    __tablename__ = "auth_events"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), index=True, nullable=True)
    ip_address = Column(String(50), nullable=True)
    event_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String(128), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
