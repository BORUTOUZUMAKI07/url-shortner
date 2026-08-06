from src.shared.errors.common import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    UnauthorizedError,
)


class URLNotFound(NotFoundError):
    def __init__(self):
        super().__init__(detail="URL not found.")


class AliasReserved(BadRequestError):
    def __init__(self, alias: str):
        super().__init__(detail=f"'{alias}' is reserved.")


class AliasConflict(ConflictError):
    def __init__(self):
        super().__init__(detail="Custom alias is already in use.")


class URLDisabled(ForbiddenError):
    def __init__(self):
        super().__init__(detail="This URL has been disabled.")


class URLExpired(BadRequestError):
    def __init__(self):
        super().__init__(detail="This URL has expired.")


class URLPasswordRequired(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Password required to access this URL.")


class URLPasswordIncorrect(UnauthorizedError):
    def __init__(self):
        super().__init__(detail="Incorrect password.")


class FolderNotInWorkspace(BadRequestError):
    def __init__(self):
        super().__init__(detail="Folder does not exist in this workspace.")


class CannotGenerateShortCode(InternalError):
    def __init__(self):
        super().__init__(detail="Could not generate a unique short code.")
