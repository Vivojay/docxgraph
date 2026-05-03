from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, JSON, UniqueConstraint, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    demographics: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptoms: Mapped[str] = mapped_column(Text)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    suspected_dx: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_dx: Mapped[str | None] = mapped_column(Text, nullable=True)
    interventions: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_differently: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    org = relationship("Org", back_populates="cases")
    author = relationship("User", back_populates="cases")
    tags = relationship("CaseTag", back_populates="case")
    revisions = relationship("CaseRevision", back_populates="case")
    validations = relationship("CaseValidation", back_populates="case")
    edges = relationship(
        "CaseEdge", back_populates="case", foreign_keys="CaseEdge.case_id"
    )


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name", "category", name="uq_tag_name_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(40))

    cases = relationship("CaseTag", back_populates="tag")


class CaseTag(Base):
    __tablename__ = "case_tags"
    __table_args__ = (UniqueConstraint("case_id", "tag_id", name="uq_case_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), index=True)

    case = relationship("Case", back_populates="tags")
    tag = relationship("Tag", back_populates="cases")


class CaseEdge(Base):
    __tablename__ = "case_edges"
    __table_args__ = (UniqueConstraint("case_id", "related_case_id", name="uq_case_edge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    related_case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    case = relationship("Case", foreign_keys=[case_id], back_populates="edges")
    related_case = relationship("Case", foreign_keys=[related_case_id])


class CaseValidation(Base):
    __tablename__ = "case_validations"
    __table_args__ = (UniqueConstraint("case_id", "doctor_id", name="uq_case_validation"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    case = relationship("Case", back_populates="validations")
    doctor = relationship("User", back_populates="validations")


class CaseRevision(Base):
    __tablename__ = "case_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    editor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    case = relationship("Case", back_populates="revisions")


class CaseViewLog(Base):
    __tablename__ = "case_view_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    viewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("orgs.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
