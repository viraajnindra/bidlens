from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import JSON, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA = Path(os.environ.get("DATA_DIR", ROOT / "data/runtime"))
DATA.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DATA / 'bidlens.db'}")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    __tablename__ = "opportunities"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    agency: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    deadline: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String, default="live")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(String, default="")
    sha256: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String, default="")
    pages: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String)


class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)
    sequence: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict] = mapped_column(JSON)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)
    facts: Mapped[dict] = mapped_column(JSON)


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[float] = mapped_column(Float)
    importance: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)


class AssessmentCache(Base):
    __tablename__ = "assessment_cache"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    result: Mapped[dict] = mapped_column(JSON)


class MappingReview(Base):
    __tablename__ = "mapping_reviews"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    requirement_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[float] = mapped_column(Float)
    body: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    opportunity_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String)
    detail: Mapped[dict] = mapped_column(JSON)


def init_db():
    Base.metadata.create_all(engine)
