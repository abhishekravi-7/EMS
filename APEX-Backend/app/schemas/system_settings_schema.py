from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

class SystemSettingsUpdate(BaseModel):
    """Payload for updating multiple system settings."""
    settings: dict[str, Optional[str]] = Field(..., description="Map of setting keys to values")

class SystemSettingsResponse(BaseModel):
    """Full set of current system settings."""
    settings: dict[str, Optional[str]]
