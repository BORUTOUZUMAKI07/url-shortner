import re
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.links.services.redirect_service import RedirectService
from src.shared import get_logger
from src.shared.core.config import settings
from src.shared.core.deps import get_redirect_service
from src.shared.core.redis import check_rate_limit
from src.shared.errors import RateLimitError, URLDisabled, URLExpired, URLNotFound, URLPasswordIncorrect

logger = get_logger(__name__)

router = APIRouter(tags=["Redirection"])

_SHORT_CODE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,32}$")

PASSWORD_PROTECTION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Protected Link - LinkForge</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
        }
        .card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 40px;
            width: 100%;
            max-width: 440px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.5);
            text-align: center;
        }
        h1 { font-size: 24px; font-weight: 700; margin: 0 0 12px 0; }
        p { font-size: 15px; color: #94a3b8; margin: 0 0 32px 0; line-height: 1.5; }
        input[type="password"] {
            width: 100%; padding: 14px 16px; background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;
            color: #ffffff; font-size: 16px; box-sizing: border-box;
        }
        button {
            width: 100%; padding: 14px; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            border: none; border-radius: 12px; color: #ffffff; font-size: 16px; font-weight: 600;
            cursor: pointer; box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4);
        }
        .error { color: #f87171; font-size: 14px; margin-top: 16px; font-weight: 500; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Link is Protected</h1>
        <p>This link requires a password to access.</p>
        <form method="POST">
            <input type="password" name="pwd" placeholder="Enter password" required autofocus>
            <button type="submit">Unlock & Redirect</button>
        </form>
        {error_placeholder}
    </div>
</body>
</html>
"""


def _validate_short_code(short_code: str) -> None:
    if not _SHORT_CODE_PATTERN.match(short_code):
        raise URLNotFound()


def _check_same_origin(request: Request) -> None:
    """Reject requests whose ``Referer`` does not match the backend origin."""
    from urllib.parse import urlparse

    referer = request.headers.get("Referer")
    if not referer:
        return
    backend_url = settings.BACKEND_URL.rstrip("/")
    backend_origin = urlparse(backend_url).hostname or ""
    referer_host = urlparse(referer).hostname or ""
    if referer_host and referer_host != backend_origin:
        from src.shared.errors import URLNotFound as _CSRFError
        raise _CSRFError()


async def _resolve_and_redirect(
    short_code: str,
    ip: str,
    user_agent: Optional[str],
    referer: Optional[str],
    pwd: Optional[str],
    svc: RedirectService,
):
    _validate_short_code(short_code)
    try:
        result = await svc.resolve(short_code, ip, user_agent, referer, pwd)
        return RedirectResponse(url=result.destination, status_code=302)
    except URLPasswordIncorrect:
        error_html = '<div class="error">Incorrect password. Please try again.</div>'
        return HTMLResponse(content=PASSWORD_PROTECTION_HTML.replace("{error_placeholder}", error_html), status_code=401)
    except URLNotFound:
        return HTMLResponse(content="<h1>404 - URL Not Found</h1>", status_code=404)
    except URLDisabled:
        return HTMLResponse(content="<h1>403 - This URL has been disabled</h1>", status_code=403)
    except URLExpired:
        return HTMLResponse(content="<h1>410 - This URL has expired</h1>", status_code=410)
    except RateLimitError:
        return HTMLResponse(content="<h1>429 - Too many requests. Please try again later.</h1>", status_code=429)


@router.get("/{short_code}",
    summary="Redirect short URL",
    description="Resolves a short code and redirects to the original URL. Supports password protection and A/B testing.",
    response_description="302 redirect to destination URL, or password-protected HTML page")
async def redirect_to_url(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user_agent: Optional[str] = Header(None),
    referer: Optional[str] = Header(None),
    svc: RedirectService = Depends(get_redirect_service),
):
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    client_host = request.client.host if request.client else "127.0.0.1"
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else client_host

    return await _resolve_and_redirect(short_code, ip, user_agent, referer, None, svc)


@router.post("/{short_code}",
    summary="Submit password for protected short URL",
    include_in_schema=False)
async def redirect_with_password(
    short_code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    pwd: str = Form(...),
    user_agent: Optional[str] = Header(None),
    referer: Optional[str] = Header(None),
    svc: RedirectService = Depends(get_redirect_service),
):
    _check_same_origin(request)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    client_host = request.client.host if request.client else "127.0.0.1"
    ip = x_forwarded_for.split(",")[0].strip() if x_forwarded_for else client_host

    rate_key = f"pw_attempt:{ip}:{short_code}"
    limited = await check_rate_limit(rate_key, capacity=10, refill_rate_per_sec=1.0 / 6.0)
    if limited:
        raise RateLimitError()

    return await _resolve_and_redirect(short_code, ip, user_agent, referer, pwd, svc)
