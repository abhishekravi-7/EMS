from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

class UserGitHubConfig(BaseModel):
    github_account: Optional[str] = None
    pat: Optional[str] = None
    pat_scope: Optional[str] = None
    repository: Optional[str] = None
    branch: Optional[str] = None
    user_access: Optional[str] = None

class UserSettingsResponse(BaseModel):
    github_config: UserGitHubConfig
    quality_checks_values: Optional[dict] = Field(default_factory=dict)
    test_cases_values: Optional[dict] = Field(default_factory=dict)
    llm_values: Optional[dict] = Field(default_factory=dict)
    system_llm_config: Optional[dict] = Field(default_factory=dict)

class UserSettingsUpdate(BaseModel):
    github_config: UserGitHubConfig
    quality_checks_values: Optional[dict] = Field(default_factory=dict)
    test_cases_values: Optional[dict] = Field(default_factory=dict)
    llm_values: Optional[dict] = Field(default_factory=dict)
