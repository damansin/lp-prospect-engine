from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, Float, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False, index=True)
    org_type = Column(Text)
    region = Column(Text)

    enrichment_data = Column(Text)       # raw JSON from LLM analysis
    aum_estimated = Column(Text)
    investment_mandate = Column(Text)
    sustainability_focus = Column(Text)
    emerging_mgr_programs = Column(Text)
    is_lp = Column(Text)                 # "Yes" / "No" / "Unclear"

    enrichment_status = Column(Text, default="pending")  # pending | enriching | done | error
    enrichment_error = Column(Text)
    enriched_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)

    contacts = relationship("Contact", back_populates="organization")
    scores = relationship("Score", back_populates="organization")


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    role = Column(Text)
    email = Column(Text)
    contact_status = Column(Text)
    relationship_depth = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

    organization = relationship("Organization", back_populates="contacts")
    score = relationship("Score", back_populates="contact", uselist=False)


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False, unique=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    sector_fit = Column(Float)
    sector_fit_reasoning = Column(Text)
    sector_fit_confidence = Column(Text)

    relationship_depth = Column(Float)

    halo_value = Column(Float)
    halo_reasoning = Column(Text)
    halo_confidence = Column(Text)

    emerging_fit = Column(Float)
    emerging_reasoning = Column(Text)
    emerging_confidence = Column(Text)

    composite_score = Column(Float)
    tier = Column(Text)

    check_size_low = Column(Float)
    check_size_high = Column(Float)

    is_anomaly = Column(Text)            # flagged anomaly description, if any
    scored_at = Column(DateTime, default=utcnow)

    contact = relationship("Contact", back_populates="score")
    organization = relationship("Organization", back_populates="scores")

    __table_args__ = (
        UniqueConstraint("contact_id", name="uq_score_contact"),
    )


class ApiCost(Base):
    __tablename__ = "api_costs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Text, nullable=False, index=True)
    service = Column(Text, nullable=False)       # "tavily" | "openai"
    operation = Column(Text, nullable=False)      # "enrichment_search" | "enrichment_analysis" | "scoring"
    organization = Column(Text)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    estimated_cost = Column(Float, default=0.0)
    timestamp = Column(DateTime, default=utcnow)
