"""
SOLID interface exports.

Import concrete service/repository implementations from their domain modules;
import abstractions (interfaces) from here.
"""

from src.shared.core.interfaces import (
    IAuditService,
    IEventDispatcher,
    IPasswordService,
    IQRCodeService,
    IRepository,
    IURLCreationService,
    IURLDeletionService,
    IURLQueryService,
    IURLRepository,
    IURLUpdateService,
    IWebhookRepository,
    IWebhookService,
    IWorkspaceRepository,
    IWorkspaceService,
)

__all__ = [
    "IRepository",
    "IURLRepository",
    "IURLCreationService",
    "IURLUpdateService",
    "IURLDeletionService",
    "IURLQueryService",
    "IQRCodeService",
    "IWorkspaceRepository",
    "IWorkspaceService",
    "IWebhookRepository",
    "IWebhookService",
    "IEventDispatcher",
    "IAuditService",
    "IPasswordService",
]
