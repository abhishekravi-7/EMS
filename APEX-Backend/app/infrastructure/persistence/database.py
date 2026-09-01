"""SQLAlchemy database engine and session setup.

For a Java developer: `engine` is roughly a JDBC DataSource/connection pool.
`SessionLocal` is a session factory, similar to a Hibernate `SessionFactory`
or a JPA `EntityManagerFactory`. Each HTTP request gets its own `Session`
(like a Hibernate `Session`/JPA `EntityManager`) via the `get_db()`
dependency below — FastAPI creates one per request and closes it afterward.
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create SQLAlchemy engine/session only when database usage is enabled and configured.
if settings.database_enabled and bool(settings.database_url):
    try:
        # `pool_pre_ping=True` makes SQLAlchemy validate a pooled connection with a
        # cheap "SELECT 1" before handing it to a request, so a connection the
        # database silently closed (e.g. after being idle) is transparently replaced
        # instead of surfacing as a request-time error.
        # Set explicit connect_timeout and pool_timeout to avoid hanging indefinitely.
        engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_timeout=10,
            connect_args={"connect_timeout": 10},
        )

        # Factory for `Session` objects — comparable to Hibernate's `SessionFactory`.
        # `autoflush=False`/`autocommit=False` are the SQLAlchemy 2.0 defaults,
        # listed explicitly here for clarity.
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not initialize database engine with provided URL: %s", exc)
        engine = None
        SessionLocal = None
else:
    engine = None  # type: Optional[object]
    SessionLocal = None


class Base(DeclarativeBase):
    """Base class every ORM model inherits from.

    `app.infrastructure.persistence.models` defines the actual tables
    (`User`, `RefreshToken`, ...) as subclasses of this `Base`.
    """


def get_db() -> Generator[Session | None, None, None]:
    """FastAPI dependency that yields one database session per request when enabled,
    or None when the database is disabled by configuration.
    """
    if not settings.database_enabled or SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_optional() -> Generator[Session | None, None, None]:
    """Optional DB dependency (alias for get_db)."""
    yield from get_db()


def _quote_identifier(name: str) -> str:
    """Safely quote a Postgres identifier (e.g. a database name) for use
    inside a DDL statement, where SQLAlchemy's normal `:param` bind
    placeholders don't work (CREATE DATABASE doesn't accept parameters).
    Doubling embedded double-quotes is Postgres's own escaping rule for
    quoted identifiers.
    """
    return '"' + name.replace('"', '""') + '"'


def ensure_database_exists() -> None:
    """Create the target PostgreSQL database if it doesn't exist yet.

    A fresh PostgreSQL install always has a default `postgres` maintenance
    database — this connects there (never to the target database, which may
    not exist yet) and issues `CREATE DATABASE` if needed. This is a local/
    dev convenience: it does NOT create the PostgreSQL user/role itself, and
    the connecting user still needs the `CREATEDB` privilege (true by
    default for a superuser like `postgres`).

    Called once at startup, before `verify_database_connection()` — see
    `app/main.py`.
    """
    if not settings.database_enabled or not settings.database_url:
        return

    try:
        target_url = make_url(settings.database_url)
        target_db_name = target_url.database
    except Exception as exc:  # noqa: BLE001
        logger.error("Could not parse DATABASE_URL: %s", exc)
        return

    if not target_db_name:
        # Nothing to create against — let verify_database_connection()
        # produce its usual clear error instead.
        return

    # `postgres` is the standard always-present maintenance database used
    # for admin operations like CREATE DATABASE — the same trick `createdb`
    # the CLI tool uses under the hood.
    maintenance_url = target_url.set(database="postgres")

    # CREATE DATABASE cannot run inside a transaction block in PostgreSQL,
    # so this connection must use autocommit rather than SQLAlchemy's
    # default (implicit transaction per statement).
    maintenance_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        with maintenance_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target_db_name},
            ).scalar_one_or_none()
            if exists is None:
                # database_name is quoted via _quote_identifier to mitigate SQL injection.
                # It is sourced from the DATABASE_URL in .env (trusted environment).
                connection.execute(text(f"CREATE DATABASE {_quote_identifier(target_db_name)}"))  # nosemgrep
                logger.info("Database '%s' did not exist — created it.", target_db_name)
    except Exception as exc:
        logger.error("Could not verify/create database '%s': %s", target_db_name, type(exc).__name__)
        raise RuntimeError(
            f"Could not connect to PostgreSQL to check/create the '{target_db_name}' database. "
            "Check DATABASE_URL's host/port/username/password in APEX-Backend/.env, confirm "
            "PostgreSQL is running, and confirm that user has the CREATEDB privilege."
        ) from exc
    finally:
        maintenance_engine.dispose()


def verify_database_connection() -> None:
    """Fail fast with a clear error if the database is unreachable.

    Called once at application startup (see `app/main.py`) so a
    misconfigured DATABASE_URL or a stopped PostgreSQL service produces an
    obvious startup error instead of a confusing failure on the first
    request.
    """
    if not settings.database_enabled or not settings.database_url or engine is None:
        return

    try:
        with engine.connect() as connection:  # type: ignore[attr-defined]
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database connection failed at startup: %s", type(exc).__name__)
        raise RuntimeError(
            "Could not connect to the database. Check DATABASE_URL in "
            "APEX-Backend/.env and confirm PostgreSQL is running."
        ) from exc
