#!/usr/bin/env python3
"""Fail when a real-looking credential is committed.

Why this exists
---------------
``.env`` is gitignored, but nothing stopped the next contributor from committing
a copy under a name the ignore rules do not cover (``secrets.env``,
``.env.backup``, a value pasted into ``README.md``). The previous gate was a
``git grep`` over eight file extensions with two whole-file exclusions, so a
credential in ``Dockerfile``, ``*.sh``, ``*.toml``, or inside either excluded
file was invisible.

This scans what git actually tracks, so an ignore rule cannot hide a leak. It is
pure stdlib and runs before any dependency install.

Design notes
------------
* **No path allowlist.** A real secret in ``docs/`` is still a leak, and a file
  that merely *mentions* a token format must not be exempt either. False
  positives are handled by matching *values*: placeholder passwords
  (``your-*``, ``changeme``, bracketed values) and ``localhost`` URIs are
  ignored, and every finding is redacted before it reaches the log.
* **No bare 40-hex rule.** Git SHAs are 40 hex characters; matching them would
  make the gate useless.
* **Fail closed.** If git itself cannot run, the scan exits 1 instead of
  reporting a clean tree.
* ``--staged`` scans only the index so ``.pre-commit-config.yaml`` can run the
  same check before a secret is ever committed.

Usage
-----
    python .github/scripts/check_secrets.py            # tracked files
    python .github/scripts/check_secrets.py --staged   # index only (pre-commit)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# A URI of the form scheme://user:password@host. Group 1 is the password,
# group 2 the host, so placeholders and CI service containers can be skipped.
URI_PASSWORD = r"[^:\s/@]*:([^@\s/]{4,})@([^\s/?#\"'<>]+)"

# Each entry: (label, compiled pattern, password group, host group).
PATTERNS: list[tuple[str, re.Pattern[str], int | None, int | None]] = [
    (
        "private key block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY-----"),
        None,
        None,
    ),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}\b"), None, None),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"), None, None),
    (
        "GitHub fine-grained PAT",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
        None,
        None,
    ),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_\-]{24,}\b"), None, None),
    ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), None, None),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), None, None),
    ("Stripe live key", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{20,}\b"), None, None),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"), None, None),
    ("Aiven service token", re.compile(r"\bAVNS_[A-Za-z0-9]{10,}\b"), None, None),
    ("Groq API key", re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), None, None),
    (
        "SendGrid API key",
        re.compile(r"\bSG\.[A-Za-z0-9_\-]{16,}\.[A-Za-z0-9_\-]{16,}\b"),
        None,
        None,
    ),
    ("New Relic user key", re.compile(r"\bNRAK-[A-Z0-9]{20,}\b"), None, None),
    (
        "Postgres URI with password",
        re.compile(r"\bpostgres(?:ql)?(?:\+[a-z0-9]+)?://" + URI_PASSWORD),
        1,
        2,
    ),
    ("MongoDB URI with password", re.compile(r"\bmongodb(?:\+srv)?://" + URI_PASSWORD), 1, 2),
    ("Redis URI with password", re.compile(r"\brediss?://" + URI_PASSWORD), 1, 2),
    ("AMQP URI with password", re.compile(r"\bamqps?://" + URI_PASSWORD), 1, 2),
]

# Generated or binary content: reading these wastes time and base64 blobs can
# contain token-shaped substrings by chance.
SKIP_SUFFIXES = (
    ".min.js",
    ".min.css",
    ".svg",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".pdf",
)
MAX_BYTES = 2_000_000

PLACEHOLDER_PASSWORDS = {
    "changeme",
    "change-me",
    "password",
    "pass",
    "secret",
    "token",
    "xxx",
    "xxxx",
    "example",
    "placeholder",
    "admin",
    "user",
    "root",
}
PLACEHOLDER_MARKERS = (
    "your",
    "changeme",
    "change-me",
    "example",
    "xxx",
    "placeholder",
    "insert",
    "replace",
    "fake",
    "dummy",
    "sample",
    "run-openssl",
    "<",
    ">",
    "****",
    "${",
    "{{",
)

# Credentials on these hosts belong to a local dev database or a CI service
# container, never an exfiltrated cloud URI.
LOCAL_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "host.docker.internal",
    "db",
    "postgres",
    "postgresql",
    "redis",
    "mongo",
    "mongodb",
    "kafka",
}


def _placeholderish(value: str) -> bool:
    normalised = value.strip().strip("<>{}[]").lower()
    if not normalised:
        return True
    if normalised in PLACEHOLDER_PASSWORDS:
        return True
    return any(marker in normalised for marker in PLACEHOLDER_MARKERS)


def _git(*args: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, check=False
        )
    except OSError as exc:  # git missing, permissions, ...
        raise RuntimeError(f"could not run git: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}): {detail}")
    return [p for p in result.stdout.decode("utf-8", "replace").split("\0") if p]


def _files(staged: bool) -> list[str]:
    if staged:
        return _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return _git("ls-files", "-z")


def _skip(rel_path: str) -> bool:
    return rel_path.lower().endswith(SKIP_SUFFIXES)


def _redact(line: str, match: re.Match[str]) -> str:
    start, end = match.span()
    hidden = "*" * min(end - start, 24)
    return (line[:start] + hidden + line[end:]).strip()[:160]


def scan(files: list[str]) -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    for rel_path in files:
        if _skip(rel_path):
            continue
        absolute = REPO_ROOT / rel_path
        try:
            if absolute.stat().st_size > MAX_BYTES:
                continue
            raw = absolute.read_bytes()
        except OSError:
            continue
        if b"\0" in raw[:8192]:  # binary
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue

        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern, group, host_group in PATTERNS:
                match = pattern.search(line)
                if match is None:
                    continue
                if group is not None and _placeholderish(match.group(group)):
                    continue
                if host_group is not None:
                    host = match.group(host_group).rsplit("@", 1)[-1]
                    if host.lower().split(":")[0] in LOCAL_HOSTS:
                        continue
                findings.append((rel_path, lineno, label, _redact(line, match)))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan tracked files for credentials.")
    parser.add_argument(
        "--staged", action="store_true", help="scan only files staged for commit"
    )
    args = parser.parse_args()

    try:
        files = _files(args.staged)
    except RuntimeError as exc:
        print(f"::error::Secret scan could not run: {exc}", file=sys.stderr)
        return 1

    findings = scan(files)
    if findings:
        print("::error::Credential-looking content found in tracked files.", file=sys.stderr)
        print(
            "Move the value into a gitignored .env, commit a placeholder instead, "
            "and rotate the credential if it was ever real.",
            file=sys.stderr,
        )
        for rel_path, lineno, label, context in findings:
            print(
                f"::error file={rel_path},line={lineno}::[{label}] {context}",
                file=sys.stderr,
            )
        print(
            f"{len(findings)} finding(s) across {len(files)} file(s) scanned.",
            file=sys.stderr,
        )
        return 1

    print(f"Clean: {len(files)} tracked file(s) scanned, no credentials found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
