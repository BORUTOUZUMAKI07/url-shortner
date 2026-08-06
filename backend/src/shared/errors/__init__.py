from src.shared.errors.auth import (
    CSRFValidationFailed,
    EmailAlreadyExists,
    InvalidCredentials,
    InvalidResetToken,
    InvalidToken,
    InvalidVerifyToken,
    OAuthFailed,
    OAuthNotConfigured,
    TokenExpired,
    TokenRevoked,
    UserNotFound,
)
from src.shared.errors.base import AppError
from src.shared.errors.common import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
)
from src.shared.errors.url import (
    AliasConflict,
    AliasReserved,
    CannotGenerateShortCode,
    FolderNotInWorkspace,
    URLDisabled,
    URLExpired,
    URLNotFound,
    URLPasswordIncorrect,
    URLPasswordRequired,
)
from src.shared.errors.workspace import (
    AlreadyMember,
    CannotInviteOwner,
    CannotRemoveOwner,
    InviteEmailMismatch,
    InviteExpired,
    InviteNotFound,
    MemberNotFound,
    OnlyAdminCanInvite,
    OnlyOwnerCanChangeRoles,
    PendingInviteExists,
    RoleTooLow,
    WorkspaceNotFound,
)

__all__ = [
    "AppError",
    "NotFoundError", "ConflictError", "BadRequestError", "ForbiddenError",
    "UnauthorizedError", "RateLimitError", "InternalError",
    "EmailAlreadyExists", "InvalidCredentials", "TokenExpired", "TokenRevoked",
    "InvalidToken", "OAuthNotConfigured", "OAuthFailed", "CSRFValidationFailed",
    "UserNotFound", "InvalidResetToken", "InvalidVerifyToken",
    "URLNotFound", "AliasReserved", "AliasConflict", "URLDisabled", "URLExpired",
    "URLPasswordRequired", "URLPasswordIncorrect", "FolderNotInWorkspace",
    "CannotGenerateShortCode",
    "WorkspaceNotFound", "OnlyAdminCanInvite", "CannotInviteOwner", "AlreadyMember",
    "PendingInviteExists", "InviteNotFound", "InviteExpired", "InviteEmailMismatch",
    "CannotRemoveOwner", "OnlyOwnerCanChangeRoles", "MemberNotFound", "RoleTooLow",
]
