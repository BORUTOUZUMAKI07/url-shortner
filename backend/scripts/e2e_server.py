#!/usr/bin/env python3
"""Boot the backend against Docker testcontainers for the frontend suites.

Intended for CI (and local developer runs): starts Postgres/Mongo/Redis
testcontainers, runs `alembic upgrade head`, then serves the real app with
uvicorn on 127.0.0.1:<E2E_PORT|8000>. The server env is scrubbed by
`build_e2e_env()` so it never touches real Neon/Atlas/Upstash/New Relic.

Usage (from the backend directory):
    uv run python scripts/e2e_server.py
"""
from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def main() -> int:
    from tests.e2e_env import build_e2e_env
    from tests.testcontainers import start_containers, stop_containers

    env = build_e2e_env()
    port = int(env.get("E2E_PORT", "8000"))
    if not _port_free(port):
        print(
            f"Port {port} is already in use (the frontend proxies to this port). "
            "Stop the other process or set E2E_PORT to a free one.",
            file=sys.stderr,
        )
        return 2

    start_containers()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "src.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
    )
    try:
        return proc.wait()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        try:
            stop_containers()
        except Exception:  # noqa: BLE001 - never mask the real exit code
            pass


if __name__ == "__main__":
    raise SystemExit(main())
