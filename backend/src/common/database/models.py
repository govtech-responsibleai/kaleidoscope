"""
SQLAlchemy ORM models for the database schema.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Enum, Float, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
import enum

from src.common.database.connection import Base


class StatusEnum(enum.Enum):
    """Status for personas and questions."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    edited = "edited"


class JobTypeEnum(enum.Enum):
    """Type of generation job."""
    persona_generation = "persona_generation"
    question_generation = "question_generation"


class JobStatusEnum(enum.Enum):
    """Status of a generation job."""
    running = "running"
    completed = "completed"
    failed = "failed"


class QuestionTypeEnum(enum.Enum):
    """Type of question."""
    typical = "typical"  # Typical use case questions
    edge = "edge"  # Edge case questions


class QuestionScopeEnum(enum.Enum):
    """Scope of question relative to knowledge base."""
    in_kb = "in_kb"  # Question about content within the knowledge base
    out_kb = "out_kb"  # Question about content outside the knowledge base


class Target(Base):
    """Target application for evaluation."""
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    agency = Column(String, nullable=True)
    purpose = Column(Text, nullable=True)
    target_users = Column(Text, nullable=True)
    api_endpoint = Column(String, nullable=True)
    endpoint_type = Column(String, nullable=True)  # "aibots", "custom_api", etc.
    endpoint_config = Column(JSON, nullable=True)  # Type-specific config
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="target", cascade="all, delete-orphan")
    personas = relationship("Persona", back_populates="target", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="target", cascade="all, delete-orphan")
    kb_documents = relationship("KnowledgeBaseDocument", back_populates="target", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Target(id={self.id}, name='{self.name}')>"


class Job(Base):
    """Generation job for personas or questions."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(JobTypeEnum), nullable=False, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True)
    count_requested = Column(Integer, nullable=False)
    model_used = Column(String, nullable=False)
    generation_prompt = Column(Text, nullable=True)
    status = Column(Enum(JobStatusEnum), default=JobStatusEnum.running, nullable=False, index=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    target = relationship("Target", back_populates="jobs")
    persona = relationship("Persona", foreign_keys=[persona_id])
    personas_generated = relationship("Persona", back_populates="job", foreign_keys="Persona.job_id")
    questions_generated = relationship("Question", back_populates="job")

    def __repr__(self):
        return f"<Job(id={self.id}, type={self.type.value}, status={self.status.value}, cost=${self.total_cost:.4f})>"


class Persona(Base):
    """Generated persona for a target application."""
    __tablename__ = "personas"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    info = Column(Text, nullable=True)
    style = Column(Text, nullable=True)
    use_case = Column(Text, nullable=True)
    status = Column(Enum(StatusEnum), default=StatusEnum.pending, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("Job", back_populates="personas_generated", foreign_keys=[job_id])
    target = relationship("Target", back_populates="personas")
    questions = relationship("Question", back_populates="persona", cascade="all, delete-orphan")

    # Unique constraint: title must be unique per target
    __table_args__ = (
        UniqueConstraint('target_id', 'title', name='uix_target_persona_title'),
    )

    def __repr__(self):
        return f"<Persona(id={self.id}, title='{self.title}', status={self.status.value})>"


class Question(Base):
    """Generated question for a persona."""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    persona_id = Column(Integer, ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    type = Column(Enum(QuestionTypeEnum), nullable=False, index=True)  # typical or edge
    scope = Column(Enum(QuestionScopeEnum), nullable=False, index=True)  # in_kb or out_kb
    status = Column(Enum(StatusEnum), default=StatusEnum.pending, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    job = relationship("Job", back_populates="questions_generated")
    persona = relationship("Persona", back_populates="questions")
    target = relationship("Target", back_populates="questions")

    def __repr__(self):
        return f"<Question(id={self.id}, persona_id={self.persona_id}, type={self.type.value}, scope={self.scope.value}, status={self.status.value})>"


class Answer(Base):
    """Generated answer from AIBots API for a question."""
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)

    # AIBots identifiers
    chat_id = Column(String, nullable=True)
    message_id = Column(String, nullable=True)

    # Important fields (extracted for easy querying)
    answer_content = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    model = Column(String, nullable=True)
    guardrails = Column(JSON, nullable=True)
    rag_citations = Column(JSON, nullable=True)

    # Full raw response for traceability
    raw_response = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    question = relationship("Question", backref="answers")
    target = relationship("Target", backref="answers")

    def __repr__(self):
        return f"<Answer(id={self.id}, question_id={self.question_id})>"


class KnowledgeBaseDocument(Base):
    """Knowledge base document for a target."""
    __tablename__ = "knowledge_base_documents"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("targets.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)  # "application/pdf", "text/plain", etc
    processed_text = Column(Text, nullable=False)  # Full extracted and cleaned text
    file_size = Column(Integer, nullable=False)  # Size in bytes
    page_count = Column(Integer, nullable=True)  # For PDFs/DOCX
    sequence_order = Column(Integer, default=0)  # For ordering multiple docs
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    target = relationship("Target", back_populates="kb_documents")

    def __repr__(self):
        return f"<KnowledgeBaseDocument(id={self.id}, target_id={self.target_id}, filename='{self.filename}')>"
