from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.core.audit_context import AuditContextData, audit_ctx_var


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ctx = AuditContextData(
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        token = audit_ctx_var.set(ctx)
        try:
            return await call_next(request)
        finally:
            audit_ctx_var.reset(token)
