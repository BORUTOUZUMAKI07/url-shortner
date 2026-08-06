from src.shared.errors.common import BadRequestError, ConflictError, UnauthorizedError


class EmailAlreadyExists(ConflictError):
    def __init__(self):
        super().__init__(detail="Email already registered.")


class InvalidCredentials(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Incorrect email or password.")


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
