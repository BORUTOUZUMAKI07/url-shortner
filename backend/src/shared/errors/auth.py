from src.shared.errors.common import BadRequestError, ConflictError, UnauthorizedError


class EmailAlreadyExists(ConflictError):
    def __init__(self):
        super().__init__(detail="Email already registered.")


class InvalidCredentials(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Incorrect email or password.")


class IncorrectCurrentPassword(BadRequestError):
    """The caller's own `current_password` did not match.

    Deliberately NOT a 401. This is raised on endpoints where the caller is
    already authenticated, so 401 is a lie about the session — and clients
    correctly treat 401 as "the session died". The frontend's fetch wrapper did
    exactly that: it refreshed, retried the request with the same wrong
    password, and then told the user "Session expired. Please login again."
    instead of pointing at the field. A wrong password on an authenticated
    endpoint is a bad request, and saying so keeps "401 means re-authenticate"
    true for every client.

    `InvalidCredentials` stays a 401 because login genuinely has no session yet.
    """

    def __init__(self):
        super().__init__(detail="Current password is incorrect.")


class TokenExpired(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Token has expired.")


class TokenRevoked(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Token has been revoked.")


class InvalidToken(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Invalid or expired token.")


class OAuthNotConfigured(BadRequestError):
    def __init__(self, provider: str):
        super().__init__(detail=f"OAuth provider '{provider}' is not configured.")


class OAuthFailed(UnauthorizedError):
    def __init__(self, provider: str):
        super().__init__(detail=f"Failed to authenticate with {provider}.")


class CSRFValidationFailed(BadRequestError):
    def __init__(self):
        super().__init__(detail="CSRF validation failed.")


class UserNotFound(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="User not found.")


class InvalidResetToken(BadRequestError):
    def __init__(self):
        super().__init__(detail="Invalid or expired reset token.")


class InvalidVerifyToken(BadRequestError):
    def __init__(self):
        super().__init__(detail="Invalid or expired verification token.")
