from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import SystemSetting


class SystemSettingsRepository:
    """Handles persistence for system-wide configuration overrides."""

    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> dict[str, str | None]:
        """Fetch all dynamic settings as a dictionary."""
        stmt = select(SystemSetting)
        rows = self.db.execute(stmt).scalars().all()
        return {r.key: r.value for r in rows}

    def get_value(self, key: str) -> str | None:
        """Fetch a single setting value by key."""
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        setting = self.db.execute(stmt).scalar_one_or_none()
        return setting.value if setting else None

    def upsert(self, key: str, value: str | None) -> None:
        """Create or update a setting."""
        existing = self.db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        ).scalar_one_or_none()

        if existing:
            existing.value = value
        else:
            self.db.add(SystemSetting(key=key, value=value))

        self.db.commit()

    def batch_update(self, settings: dict[str, str | None]) -> None:
        """Update multiple settings in a single transaction."""
        for key, value in settings.items():
            self.upsert(key, value)
