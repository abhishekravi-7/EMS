from contextvars import ContextVar
from typing import Optional

user_id_ctx: ContextVar[Optional[int]] = ContextVar("user_id_ctx", default=None)
job_id_ctx: ContextVar[Optional[str]] = ContextVar("job_id_ctx", default=None)
repository_url_ctx: ContextVar[Optional[str]] = ContextVar("repository_url_ctx", default=None)
llm_values_ctx: ContextVar[dict] = ContextVar("llm_values_ctx", default={})
