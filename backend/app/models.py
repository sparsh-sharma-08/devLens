"""
DevLens AI — SQLAlchemy ORM Models
All 11 tables from the Database Design document (05-Database-Design.md).
"""
import uuid
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. users
# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    # bcrypt-hashed password — only set for email/password users; NULL for OAuth-only users
    password_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    repositories: Mapped[list["Repository"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    conversations: Mapped[list["ChatConversation"]] = relationship(back_populates="user")


# ─────────────────────────────────────────────────────────────────────────────
# 2. repositories
# ─────────────────────────────────────────────────────────────────────────────
class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False)  # e.g. "octocat/devlens-ai"
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_kb: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    primary_language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    languages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # {"Python": 70, "JS": 30}
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending|indexing|ready|failed
    health_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_indexed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="repositories")
    files: Mapped[list["File"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    indexing_jobs: Mapped[list["IndexingJob"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    graph_nodes: Mapped[list["GraphNode"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    graph_edges: Mapped[list["GraphEdge"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    static_analysis_results: Mapped[list["StaticAnalysisResult"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    health_reports: Mapped[list["HealthReport"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    conversations: Mapped[list["ChatConversation"]] = relationship(back_populates="repository", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_user_id", "source_url", name="uq_user_repo_url"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. indexing_jobs
# ─────────────────────────────────────────────────────────────────────────────
class IndexingJob(Base):
    __tablename__ = "indexing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(String(100), default="pending")
    # Stages: pending|cloning|detecting_language|parsing|building_graph|embedding|static_analysis|report_generation|done|failed
    progress_pct: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="indexing_jobs")


# ─────────────────────────────────────────────────────────────────────────────
# 4. files
# ─────────────────────────────────────────────────────────────────────────────
class File(Base):
    __tablename__ = "files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(Text, nullable=False)  # relative path within repo
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    loc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # git blob sha

    repository: Mapped["Repository"] = relationship(back_populates="files")
    graph_nodes: Mapped[list["GraphNode"]] = relationship(back_populates="file")
    static_analysis_results: Mapped[list["StaticAnalysisResult"]] = relationship(back_populates="file")


# ─────────────────────────────────────────────────────────────────────────────
# 5. graph_nodes
# ─────────────────────────────────────────────────────────────────────────────
class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    node_type: Mapped[str] = mapped_column(String(50))  # file|class|function|method|module|route
    name: Mapped[str] = mapped_column(String(512))
    qualified_name: Mapped[str] = mapped_column(Text)  # unique per repo
    start_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="graph_nodes")
    file: Mapped[Optional["File"]] = relationship(back_populates="graph_nodes")
    outgoing_edges: Mapped[list["GraphEdge"]] = relationship(
        foreign_keys="GraphEdge.source_node_id", back_populates="source_node", cascade="all, delete-orphan"
    )
    incoming_edges: Mapped[list["GraphEdge"]] = relationship(
        foreign_keys="GraphEdge.target_node_id", back_populates="target_node"
    )
    embeddings: Mapped[list["Embedding"]] = relationship(back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("repository_id", "qualified_name", name="uq_repo_qualified_name"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. graph_edges
# ─────────────────────────────────────────────────────────────────────────────
class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    source_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    edge_type: Mapped[str] = mapped_column(String(50))  # calls|imports|extends|implements|defines|depends_on
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    repository: Mapped["Repository"] = relationship(back_populates="graph_edges")
    source_node: Mapped["GraphNode"] = relationship(foreign_keys=[source_node_id], back_populates="outgoing_edges")
    target_node: Mapped["GraphNode"] = relationship(foreign_keys=[target_node_id], back_populates="incoming_edges")


# ─────────────────────────────────────────────────────────────────────────────
# 7. embeddings
# ─────────────────────────────────────────────────────────────────────────────
class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    node_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50))  # code|documentation
    content_excerpt: Mapped[str] = mapped_column(Text)
    vector: Mapped[list[float]] = mapped_column(Vector(384))  # all-MiniLM-L6-v2 dimension

    repository: Mapped["Repository"] = relationship(back_populates="embeddings")
    node: Mapped[Optional["GraphNode"]] = relationship(back_populates="embeddings")


# ─────────────────────────────────────────────────────────────────────────────
# 8. static_analysis_results
# ─────────────────────────────────────────────────────────────────────────────
class StaticAnalysisResult(Base):
    __tablename__ = "static_analysis_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    tool: Mapped[str] = mapped_column(String(50))  # ruff|bandit|eslint
    file_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    line: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(20))  # critical|high|medium|low|info
    rule_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship(back_populates="static_analysis_results")
    file: Mapped[Optional["File"]] = relationship(back_populates="static_analysis_results")


# ─────────────────────────────────────────────────────────────────────────────
# 9. health_reports
# ─────────────────────────────────────────────────────────────────────────────
class HealthReport(Base):
    __tablename__ = "health_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    overall_score: Mapped[int] = mapped_column(Integer)  # 0–100
    complexity_score: Mapped[int] = mapped_column(Integer)
    security_score: Mapped[int] = mapped_column(Integer)
    duplication_score: Mapped[int] = mapped_column(Integer)
    dependency_score: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="health_reports")


# ─────────────────────────────────────────────────────────────────────────────
# 10. chat_conversations
# ─────────────────────────────────────────────────────────────────────────────
class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    repository: Mapped["Repository"] = relationship(back_populates="conversations")
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


# ─────────────────────────────────────────────────────────────────────────────
# 11. chat_messages
# ─────────────────────────────────────────────────────────────────────────────
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    citations_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")
