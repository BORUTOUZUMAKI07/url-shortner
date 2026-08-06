import contextvars
from dataclasses import dataclass


@dataclass
class AuditContextData:
    ip_address: str | None = None
    user_agent: str | None = None


audit_ctx_var: contextvars.ContextVar[AuditContextData | None] = contextvars.ContextVar("audit_ctx", default=None)
