from typing import Optional


class AppError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        headers: Optional[dict[str, str]] = None,
    ):
        self.detail = detail
        self.status_code = status_code
        self.error_code = error_code
        # Response headers carried onto the 4xx/5xx response (e.g. Retry-After
        # on a 429). The handler in main.py merges these — raising an AppError
        # with headers must not silently drop them.
        self.headers = headers
        super().__init__(detail)
