import pytest

from src.errors import (
    AliasConflict,
    AliasReserved,
    AlreadyMember,
    AppError,
    BadRequestError,
    CSRFValidationFailed,
    CannotGenerateShortCode,
    CannotInviteOwner,
    CannotRemoveOwner,
    ConflictError,
    EmailAlreadyExists,
    FolderNotInWorkspace,
    ForbiddenError,
    InternalError,
    InvalidCredentials,
    InvalidResetToken,
    InvalidToken,
    InvalidVerifyToken,
    InviteEmailMismatch,
    InviteExpired,
    InviteNotFound,
    MemberNotFound,
    NotFoundError,
    OAuthFailed,
    OAuthNotConfigured,
    OnlyAdminCanInvite,
    OnlyOwnerCanChangeRoles,
    PendingInviteExists,
    RateLimitError,
    RoleTooLow,
    TokenExpired,
    TokenRevoked,
    URLDisabled,
    URLExpired,
    URLNotFound,
    URLPasswordIncorrect,
    URLPasswordRequired,
    UnauthorizedError,
    UserNotFound,
    WorkspaceNotFound,
)


class TestAppError:
    def test_default_attributes(self):
        err = AppError("Something broke")
        assert err.detail == "Something broke"
        assert err.status_code == 500
        assert err.error_code == "INTERNAL_ERROR"

    def test_custom_attributes(self):
        err = AppError("Custom error", status_code=418, error_code="TEAPOT")
        assert err.detail == "Custom error"
        assert err.status_code == 418
        assert err.error_code == "TEAPOT"

    def test_is_exception(self):
        assert issubclass(AppError, Exception)


class TestCommonErrors:
    def test_not_found_error(self):
        err = NotFoundError()
        assert err.detail == "Resource not found."
        assert err.status_code == 404
        assert err.error_code == "NOT_FOUND"

    def test_not_found_error_custom(self):
        err = NotFoundError("User not found.")
        assert err.detail == "User not found."

    def test_conflict_error(self):
        err = ConflictError()
        assert err.detail == "Resource already exists."
        assert err.status_code == 409
        assert err.error_code == "CONFLICT"

    def test_bad_request_error(self):
        err = BadRequestError()
        assert err.detail == "Bad request."
        assert err.status_code == 400
        assert err.error_code == "BAD_REQUEST"

    def test_forbidden_error(self):
        err = ForbiddenError()
        assert err.detail == "Access denied."
        assert err.status_code == 403
        assert err.error_code == "FORBIDDEN"

    def test_unauthorized_error(self):
        err = UnauthorizedError()
        assert err.detail == "Not authenticated."
        assert err.status_code == 401
        assert err.error_code == "UNAUTHORIZED"

    def test_rate_limit_error(self):
        err = RateLimitError()
        assert err.detail == "Rate limit exceeded. Try again later."
        assert err.status_code == 429
        assert err.error_code == "RATE_LIMITED"

    def test_internal_error(self):
        err = InternalError()
        assert err.detail == "Internal server error."
        assert err.status_code == 500
        assert err.error_code == "INTERNAL_ERROR"

    def test_error_hierarchy(self):
        assert issubclass(NotFoundError, AppError)
        assert issubclass(ConflictError, AppError)
        assert issubclass(BadRequestError, AppError)
        assert issubclass(ForbiddenError, AppError)
        assert issubclass(UnauthorizedError, AppError)
        assert issubclass(RateLimitError, AppError)
        assert issubclass(InternalError, AppError)

    def test_custom_detail_messages(self):
        assert ForbiddenError("Custom forbidden").detail == "Custom forbidden"
        assert NotFoundError("Custom not found").detail == "Custom not found"
        assert BadRequestError("Custom bad request").detail == "Custom bad request"
        assert UnauthorizedError("Custom unauthorized").detail == "Custom unauthorized"


class TestAuthErrors:
    def test_email_already_exists(self):
        err = EmailAlreadyExists()
        assert err.detail == "Email already registered."
        assert err.status_code == 409
        assert err.error_code == "CONFLICT"
        assert isinstance(err, ConflictError)

    def test_invalid_credentials(self):
        err = InvalidCredentials()
        assert err.detail == "Incorrect email or password."
        assert err.status_code == 401
        assert err.error_code == "UNAUTHORIZED"
        assert isinstance(err, UnauthorizedError)

    def test_token_expired(self):
        err = TokenExpired()
        assert err.detail == "Token has expired."
        assert err.status_code == 401
        assert err.error_code == "UNAUTHORIZED"

    def test_token_revoked(self):
        err = TokenRevoked()
        assert err.detail == "Token has been revoked."
        assert err.status_code == 401

    def test_invalid_token(self):
        err = InvalidToken()
        assert err.detail == "Invalid or expired token."
        assert err.status_code == 401

    def test_oauth_not_configured(self):
        err = OAuthNotConfigured("google")
        assert err.detail == "OAuth provider 'google' is not configured."
        assert err.status_code == 400
        assert isinstance(err, BadRequestError)

    def test_oauth_failed(self):
        err = OAuthFailed("github")
        assert err.detail == "Failed to authenticate with github."
        assert err.status_code == 401

    def test_csrf_validation_failed(self):
        err = CSRFValidationFailed()
        assert err.detail == "CSRF validation failed."
        assert err.status_code == 400

    def test_user_not_found(self):
        err = UserNotFound()
        assert err.detail == "User not found."
        assert err.status_code == 401

    def test_invalid_reset_token(self):
        err = InvalidResetToken()
        assert err.detail == "Invalid or expired reset token."
        assert err.status_code == 400

    def test_invalid_verify_token(self):
        err = InvalidVerifyToken()
        assert err.detail == "Invalid or expired verification token."
        assert err.status_code == 400

    def test_auth_error_hierarchy(self):
        assert issubclass(EmailAlreadyExists, ConflictError)
        assert issubclass(InvalidCredentials, UnauthorizedError)
        assert issubclass(TokenExpired, UnauthorizedError)
        assert issubclass(TokenRevoked, UnauthorizedError)
        assert issubclass(InvalidToken, UnauthorizedError)
        assert issubclass(OAuthNotConfigured, BadRequestError)
        assert issubclass(OAuthFailed, UnauthorizedError)
        assert issubclass(CSRFValidationFailed, BadRequestError)
        assert issubclass(UserNotFound, UnauthorizedError)
        assert issubclass(InvalidResetToken, BadRequestError)
        assert issubclass(InvalidVerifyToken, BadRequestError)


class TestURLErrors:
    def test_url_not_found(self):
        err = URLNotFound()
        assert err.detail == "URL not found."
        assert err.status_code == 404
        assert err.error_code == "NOT_FOUND"

    def test_alias_reserved(self):
        err = AliasReserved("admin")
        assert err.detail == "'admin' is reserved."
        assert err.status_code == 400

    def test_alias_conflict(self):
        err = AliasConflict()
        assert err.detail == "Custom alias is already in use."
        assert err.status_code == 409

    def test_url_disabled(self):
        err = URLDisabled()
        assert err.detail == "This URL has been disabled."
        assert err.status_code == 403

    def test_url_expired(self):
        err = URLExpired()
        assert err.detail == "This URL has expired."
        assert err.status_code == 400

    def test_url_password_required(self):
        err = URLPasswordRequired()
        assert err.detail == "Password required to access this URL."
        assert err.status_code == 401

    def test_url_password_incorrect(self):
        err = URLPasswordIncorrect()
        assert err.detail == "Incorrect password."
        assert err.status_code == 401

    def test_folder_not_in_workspace(self):
        err = FolderNotInWorkspace()
        assert err.detail == "Folder does not exist in this workspace."
        assert err.status_code == 400

    def test_cannot_generate_short_code(self):
        err = CannotGenerateShortCode()
        assert err.detail == "Could not generate a unique short code."
        assert err.status_code == 500

    def test_url_error_hierarchy(self):
        assert issubclass(URLNotFound, NotFoundError)
        assert issubclass(AliasReserved, BadRequestError)
        assert issubclass(AliasConflict, ConflictError)
        assert issubclass(URLDisabled, ForbiddenError)
        assert issubclass(URLExpired, BadRequestError)
        assert issubclass(URLPasswordRequired, UnauthorizedError)
        assert issubclass(URLPasswordIncorrect, UnauthorizedError)
        assert issubclass(FolderNotInWorkspace, BadRequestError)
        assert issubclass(CannotGenerateShortCode, InternalError)


class TestWorkspaceErrors:
    def test_workspace_not_found(self):
        err = WorkspaceNotFound()
        assert err.detail == "Workspace not found or access denied."
        assert err.status_code == 404

    def test_only_admin_can_invite(self):
        err = OnlyAdminCanInvite()
        assert err.detail == "Only admins can invite members."
        assert err.status_code == 403

    def test_cannot_invite_owner(self):
        err = CannotInviteOwner()
        assert err.detail == "Cannot invite the workspace owner."
        assert err.status_code == 409

    def test_already_member(self):
        err = AlreadyMember()
        assert err.detail == "User is already a member of this workspace."
        assert err.status_code == 409

    def test_pending_invite_exists(self):
        err = PendingInviteExists()
        assert err.detail == "A pending invite already exists for this email."
        assert err.status_code == 409

    def test_invite_not_found(self):
        err = InviteNotFound()
        assert err.detail == "Invite not found."
        assert err.status_code == 404

    def test_invite_expired(self):
        err = InviteExpired()
        assert err.detail == "Invite has expired."
        assert err.status_code == 400

    def test_invite_email_mismatch(self):
        err = InviteEmailMismatch()
        assert err.detail == "This invite was sent to a different email address."
        assert err.status_code == 403

    def test_cannot_remove_owner(self):
        err = CannotRemoveOwner()
        assert err.detail == "Cannot remove the workspace owner."
        assert err.status_code == 400

    def test_only_owner_can_change_roles(self):
        err = OnlyOwnerCanChangeRoles()
        assert err.detail == "Only the workspace owner can change roles."
        assert err.status_code == 403

    def test_member_not_found(self):
        err = MemberNotFound()
        assert err.detail == "Member not found."
        assert err.status_code == 404

    def test_role_too_low(self):
        err = RoleTooLow("editor")
        assert err.detail == "Requires editor role or higher."
        assert err.status_code == 403

    def test_workspace_error_hierarchy(self):
        assert issubclass(WorkspaceNotFound, NotFoundError)
        assert issubclass(OnlyAdminCanInvite, ForbiddenError)
        assert issubclass(CannotInviteOwner, ConflictError)
        assert issubclass(AlreadyMember, ConflictError)
        assert issubclass(PendingInviteExists, ConflictError)
        assert issubclass(InviteNotFound, NotFoundError)
        assert issubclass(InviteExpired, BadRequestError)
        assert issubclass(InviteEmailMismatch, ForbiddenError)
        assert issubclass(CannotRemoveOwner, BadRequestError)
        assert issubclass(OnlyOwnerCanChangeRoles, ForbiddenError)
        assert issubclass(MemberNotFound, NotFoundError)
        assert issubclass(RoleTooLow, ForbiddenError)


class TestAppErrorStringRepresentation:
    def test_str_representation(self):
        err = AppError("test")
        assert str(err) == "test"
        assert repr(err).startswith("AppError(")
