"""SQLAlchemy ORM models — the actual database tables.

For a Java developer: each class below is the equivalent of a JPA `@Entity`
class. `Mapped[...]` + `mapped_column(...)` declare a column and its Python
type together (SQLAlchemy 2.0's typed style), similar to a JPA field with a
`@Column` annotation.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.database import Base


def _utc_now() -> datetime:
    """Current time, timezone-aware, in UTC. Used as a column default."""
    return datetime.now(timezone.utc)


class User(Base):
    """A registered account.

    `auth_provider` is "local" for an email/password account, or "google"/
    "github" for one created via social login (see `OAuthAccount` below and
    `app.application.services.auth_service.AuthService.authenticate_with_oauth`).
    `password_hash` is nullable because an OAuth-only user never has one —
    Google/GitHub passwords are never seen or stored by this app.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # unique + index: no two users can share an email, and email lookups
    # (login) are fast. Always stored trimmed + lowercase by the schema layer.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local", server_default="local")
    provider_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="USER", server_default="USER")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # One user can have many refresh tokens (one per browser/device session).
    # cascade="all, delete-orphan" mirrors JPA's `cascade = CascadeType.ALL,
    # orphanRemoval = true`: deleting a User also deletes their RefreshToken
    # rows at the ORM level. The FK below additionally does this at the
    # database level (`ondelete="CASCADE"`), so it holds even for deletes
    # that bypass the ORM.
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """One row per issued refresh token. Stores only a hash — never the
    original token (see `app.core.security.hash_refresh_token`)."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_token_hash", "token_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL while the token is active; set to the revocation time once it has
    # been rotated (see /api/auth/refresh) or the user has logged out.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class OAuthAccount(Base):
    """Links a local `User` to one Google/GitHub identity.

    The unique constraint on `(provider, provider_user_id)` is what makes
    "find the user for this provider identity" a safe, race-free lookup —
    it's also the constraint that guarantees a repeat login for the same
    provider account can never create a second user (see
    `app.application.services.auth_service.AuthService.authenticate_with_oauth`).
    Never stores a password. Never stores the provider's own access/refresh
    token — this app only ever needs the profile fetched at login time.
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_accounts_provider_identity"),
        Index("ix_oauth_accounts_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # "google" or "github".
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # The provider's own stable user id (Google's `sub`, GitHub's numeric `id`) —
    # never the user's email, which the user could change with the provider.
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )

    user: Mapped["User"] = relationship()


class MigrationJobOwner(Base):
    """Maps a filesystem-stored migration `job_id` to the user who created it.

    Migration job data itself is unchanged — it still lives on disk as JSON
    reports under `storage/migration-jobs/<jobId>/` (see
    `app.infrastructure.persistence.job_repository.JobRepository`). This
    table exists solely to answer "which user created job X", so the
    Discovery/Migration/Docs endpoints can verify the caller is allowed to
    see a given job instead of trusting a job id alone (job ids are
    unguessable UUIDs, but not a substitute for real authorization).
    """

    __tablename__ = "migration_job_owners"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now)


class LLMTokenUsage(Base):
    """Tracks token usage for all LLM requests (Ollama and Groq).
    
    Records metadata for every LLM call including token counts, provider,
    model, duration, and fallback information. Used for monitoring LLM
    usage and cost tracking in the Strategy chatbot.
    """

    __tablename__ = "llm_token_usage"
    __table_args__ = (
        Index("ix_llm_token_usage_user_created", "user_id", "created_at"),
        Index("ix_llm_token_usage_repo_url", "repository_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Request correlation ID for grouping related requests (e.g., original + fallback)
    request_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # User who initiated the LLM request (if available)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # Job ID from migration workflow (if applicable)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Timestamp of the request
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utc_now, index=True)
    
    # Provider identification
    provider: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # "ollama" or "groq"
    model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Token counts from provider response (nullable for Ollama if not available)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(nullable=True)
    # Prompt cache hit tokens (for providers that support prompt caching)
    cached_tokens: Mapped[int | None] = mapped_column(nullable=True)
    
    # Request metadata
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")  # e.g., "chat", "system"
    endpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)  # API endpoint name
    call_type: Mapped[str] = mapped_column(String(50), nullable=False, default="chat_stream")
    
    # Execution metrics
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)  # Response time in milliseconds
    estimated_cost_usd: Mapped[float | None] = mapped_column(nullable=True)  # Estimated cost
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="success", index=True)  # "success" or "failure"
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Fallback tracking
    fallback_used: Mapped[bool] = mapped_column(nullable=False, default=False)  # Was fallback to Groq used?
    fallback_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Why fallback occurred
    original_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # Original provider before fallback
    
    # Attempt tracking (for retries)
    attempt: Mapped[int] = mapped_column(nullable=False, default=1)
    is_retry: Mapped[bool] = mapped_column(nullable=False, default=False)
    
    # Additional context
    question_preview: Mapped[str | None] = mapped_column(String(500), nullable=True)  # First 500 chars of question
    repository_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # Repository being analyzed


class PersistedMigrationReport(Base):
    """Stores the latest migration report JSON for a job in PostgreSQL.

    Ensures that when DigitalOcean load-balances requests across multiple
    containers or if a container is restarted, any container can immediately
    read and serve the migration status/summary without returning 404.
    """

    __tablename__ = "persisted_migration_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="QUEUED")
    progress_percent: Mapped[int] = mapped_column(nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(50), nullable=True)
    report_json: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now, onupdate=_utc_now
    )
