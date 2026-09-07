"""Backend E2E tests: boot a real uvicorn server against Docker testcontainers.

These tests exercise the full HTTP stack (middleware, rate limiting, auth
cookies, redirects) against a real server process — not the ASGI test client.
They are NOT covered by the in-process `mock_external_services` fixture
patches (the server is a separate process), so they use the real argon2
hashing, real Redis/Mongo, and real SMTP-less email service.

Run only with Docker:
    uv run pytest tests/test_e2e -v --use-testcontainers
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from tests.e2e_env import build_e2e_env

BACKEND_DIR = Path(__file__).resolve().parents[2]
PORT = os.environ.get("E2E_BACKEND_PORT", "8001")
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture(scope="session")
def server():
    """Boot the real app with uvicorn against the testcontainer-backed env."""
    env = build_e2e_env()
    env["E2E_BACKEND_PORT"] = PORT
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            PORT,
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
    )
    try:
        _wait_ready(proc)
        yield BASE_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def _wait_ready(proc: subprocess.Popen) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"uvicorn exited at startup with code {proc.returncode}")
        try:
            resp = httpx.get(f"{BASE_URL}/api/v1/ping", timeout=5)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("uvicorn did not become ready in time (120s)")
