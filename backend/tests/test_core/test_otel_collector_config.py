"""Guards for `docker/otel-collector-config.yaml`.

Three strengths of protection, weakest to strongest:

* the static shape assertions pin behaviour that is invisible when reverted
  (basicauth on the receiver, gzip export, the percentage memory limiter, the
  in-memory queue, no Prometheus scrape pipeline);
* `test_every_resource_attribute_declares_an_action` names the exact field a
  known startup rejection was caused by, so the message says *which* entry is
  wrong rather than "the collector did not become ready";
* `test_the_collector_really_builds_the_tracked_config` starts the pinned image
  on the tracked file and waits for readiness. This is the one that matters:
  `otelcol validate` exits 0 on a config that dies while *building* the
  pipeline graph, so a validate-based guard passes against the very defect it
  was written for. It asks the collector itself instead of asserting the shape
  a repo test claims to want. Skips — never fails — without Docker.

None of these prove telemetry reaches New Relic; that needs a live ingest key
and network, which is a deployment step, not a test dependency.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import uuid
import warnings
from pathlib import Path

import pytest
import yaml

from src.shared.core.config import warn_if_default_otlp_credential

REPO_ROOT = Path(__file__).resolve().parents[3]
COLLECTOR_CONFIG = REPO_ROOT / "docker" / "otel-collector-config.yaml"
RENDER_YAML = REPO_ROOT / "backend" / "render.yaml"

# The tag docker-compose.yml mounts, so the image and the config file move
# together or not at all.
IMAGE = "otel/opentelemetry-collector-contrib:0.121.0"

# The only values the resource processor's `action` field accepts.
ALLOWED_ACTIONS = frozenset({"insert", "update", "upsert", "delete"})

# Readiness lands well under a second after start; a rejected config exits
# immediately. Polling for the marker keeps a healthy run quick and a broken
# one fast, and bounds both.
STARTUP_TIMEOUT_SECONDS = 20.0
POLL_INTERVAL_SECONDS = 0.5
READY_MARKER = "Everything is ready"

_DEV_HEADER = "Authorization=Basic bGlua2ZvcmdlOmxpbmtmb3JnZQ=="


def _config() -> dict:
    return yaml.safe_load(COLLECTOR_CONFIG.read_text(encoding="utf-8"))


def test_collector_config_has_basicauth_and_no_scrape() -> None:
    data = _config()
    # basicauth extension exists
    assert "extensions" in data
    assert "basicauth/server" in data["extensions"]
    # otlp http has auth
    otlp = data["receivers"]["otlp"]
    assert otlp["protocols"]["http"]["auth"]["authenticator"] == "basicauth/server"
    # no prometheus receiver
    assert "prometheus" not in data["receivers"]
    # no metrics/scrape pipeline
    pipelines = data["service"]["pipelines"]
    for name in pipelines:
        assert name != "metrics/scrape"


def test_collector_hardening_is_wired() -> None:
    """Pin the settings whose removal produces no visible failure.

    Dropping gzip, the in-memory queue or the percentage limiter still leaves a
    collector that forwards telemetry — until a burst or a big instance, when
    it OOMs or silently stops exporting. Static, so it names the missing piece
    with no Docker involved.
    """
    data = _config()

    # 1. Percentage memory limit: one file must be correct at every instance
    # size. A fixed limit_mib is pinned to whichever machine it was tuned on.
    limiter = data["processors"]["memory_limiter"]
    assert limiter.get("limit_percentage"), (
        "processors.memory_limiter must use limit_percentage (75% of the "
        "container's memory), not a fixed limit_mib pinned to one instance size"
    )
    assert limiter.get("spike_limit_percentage"), (
        "processors.memory_limiter must set spike_limit_percentage so a burst "
        "has bounded headroom above the soft limit"
    )
    assert not limiter.get("limit_mib"), (
        "limit_mib and limit_percentage are mutually exclusive; keep the "
        "percentage form"
    )

    # 2. gzip to the vendor: fewer bytes over the wire for the same telemetry.
    exporter = data["exporters"]["otlphttp/newrelic"]
    assert exporter.get("compression") == "gzip", (
        "exporters.otlphttp/newrelic must gzip; the ingest link is the one "
        "place compression is free"
    )

    # 3. In-memory queue only — deliberately NOT file_storage, because the
    # upstream image is scratch with no writable directory and a Render
    # free-tier disk is ephemeral (so durability would be a claim this
    # deployment cannot make). Pinned so the comment and the config cannot
    # drift apart.
    queue = exporter.get("sending_queue") or {}
    assert queue.get("enabled") is True
    assert "storage" not in queue, (
        "the sending queue is a smoothing buffer, not durable delivery: "
        "docker/otel-collector-config.yaml documents why file_storage is "
        "omitted, and this assert keeps the config honest"
    )

    # 4. Traces keep errors, slow requests and a sample of the rest.
    policies = {p.get("name"): p.get("type") for p in data["processors"]["tail_sampling"]["policies"]}
    assert policies.get("keep-errors") == "status_code"
    assert policies.get("keep-slow") == "latency", (
        "tail_sampling must keep slow traces: under load, a plain "
        "'errors + N%' policy drops exactly the spans that explain a p99 "
        "regression"
    )
    assert policies.get("sample-rest") == "probabilistic"


def test_every_resource_attribute_declares_an_action() -> None:
    """Name the field, with no Docker involved.

    Narrow by design: it knows one schema requirement, and would not notice a
    different build-time error. The startup test below covers the class; this
    one exists so the failure message points at the offending entry.
    """
    resource = (_config().get("processors") or {}).get("resource")
    assert resource, (
        "processors.resource is missing; every pipeline lists it, so the "
        "collector would not start"
    )
    attributes = resource.get("attributes") or []
    assert attributes, "processors.resource.attributes is empty; nothing would be checked"

    for index, entry in enumerate(attributes):
        assert "action" in entry, (
            f"processors.resource.attributes[{index}] (key={entry.get('key')!r}) omits "
            "`action`. collector-contrib v0.121.0 then builds an empty action and "
            'refuses to start: failed to create "resource" processor ... '
            'unsupported action "" — the container exits 1 before /healthz, and the '
            "only symptom is telemetry that never arrives."
        )
        assert entry["action"] in ALLOWED_ACTIONS, (
            f"processors.resource.attributes[{index}] has action={entry['action']!r}; "
            f"one of {sorted(ALLOWED_ACTIONS)} is required"
        )


# --------------------------------------------------------------------------
# The credential warning (shared/core/config.py) — non-local endpoint only.
# --------------------------------------------------------------------------


def test_dev_credential_with_public_endpoint_warns() -> None:
    with pytest.warns(UserWarning, match="published in this repo"):
        warn_if_default_otlp_credential(
            endpoint="https://linkforge-otel-collector.onrender.com",
            headers=_DEV_HEADER,
        )


def test_empty_header_with_public_endpoint_warns() -> None:
    """A blueprint var left blank must not fail silently as 401s."""
    with pytest.warns(UserWarning, match="basicauth"):
        warn_if_default_otlp_credential(
            endpoint="https://linkforge-otel-collector.onrender.com",
            headers="",
        )


def test_dev_credential_with_local_endpoint_is_silent() -> None:
    for endpoint in (
        "http://localhost:4318",
        "http://otel-collector:4318",
        "http://127.0.0.1:4318",
    ):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            warn_if_default_otlp_credential(endpoint=endpoint, headers=_DEV_HEADER)


def test_non_dev_header_is_silent() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        warn_if_default_otlp_credential(
            endpoint="https://otlp.nr-data.net:4318",
            headers="api-key=<ingest-key>",
        )


def _render_services() -> dict[str, dict]:
    data = yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))
    return {service["name"]: service for service in data["services"]}


def _env_var(service: dict, key: str) -> dict:
    matches = [entry for entry in service["envVars"] if entry["key"] == key]
    assert len(matches) == 1, f"expected exactly one {key} on {service['name']}, found {len(matches)}"
    return matches[0]


def test_render_blueprint_does_not_commit_the_receiver_credential() -> None:
    """Both halves of the OTLP credential must be prompted, never committed.

    render.yaml is public and it deploys a public collector, so a committed
    ``value:`` on either side is a published password on a receiver anyone can
    reach. This is a security property that produced no failure when it was
    wrong — the stack worked — so it needs a guard rather than a comment.
    """
    backend = _env_var(_render_services()["linkforge-backend"], "OTEL_EXPORTER_OTLP_HEADERS")
    assert backend.get("sync") is False, "OTEL_EXPORTER_OTLP_HEADERS must be prompted (sync: false)"
    assert "value" not in backend, (
        "OTEL_EXPORTER_OTLP_HEADERS must not commit a value: render.yaml is public and the "
        "collector it deploys is public, so a committed Authorization header is a password "
        "published to everyone who can read this repo. Leave it blank and let the startup "
        "warning name the fallback."
    )

    collector = _env_var(
        _render_services()["linkforge-otel-collector"], "OTLP_HTTP_AUTH_HTPASSWD"
    )
    assert collector.get("sync") is False, "OTLP_HTTP_AUTH_HTPASSWD must be prompted (sync: false)"
    assert "value" not in collector, (
        "OTLP_HTTP_AUTH_HTPASSWD must not commit a value: the collector's public OTLP receiver "
        "would then be guarded by a credential in the repo (the config file already documents "
        "the `linkforge:linkforge` fallback for local use)."
    )


# --------------------------------------------------------------------------
# The integration guard: the collector itself must build the tracked config.
# --------------------------------------------------------------------------


def _docker(args: list[str], timeout: float = 60) -> subprocess.CompletedProcess[str]:
    """Run a docker subcommand, capturing both streams as text.

    `encoding`/`errors` are explicit: on Windows the child's output is not
    reliably UTF-8, and a decode error here would look like a Docker failure.
    """
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _require_docker() -> None:
    """Skip — never fail — when Docker itself is unavailable.

    This test is about a config file. Going red because the daemon is down
    would teach people to ignore the signal that matters.
    """
    if shutil.which("docker") is None:
        pytest.skip("docker is not on PATH; the collector startup check needs it")

    try:
        probe = _docker(["info"], timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"docker is not runnable: {type(exc).__name__}: {exc}")
    if probe.returncode != 0:
        pytest.skip("docker daemon is not running (environment, not a regression)")

    # The image is a few hundred MB; only pay for it if it is genuinely missing,
    # and skip (with the reason) rather than fail when the network cannot supply
    # it — "no image" is not "the config is broken".
    if _docker(["image", "inspect", IMAGE], timeout=60).returncode == 0:
        return
    try:
        pull = _docker(["pull", IMAGE], timeout=600)
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"cannot pull {IMAGE}: {type(exc).__name__}: {exc}")
    if pull.returncode != 0:
        pytest.skip(f"cannot pull {IMAGE}: {pull.stderr.strip()[:300]}")


def _wait_until_ready(name: str) -> str | None:
    """Poll the container; `None` means readiness, else a failure reason.

    Readiness is the property under test, not liveness: the collector prints
    the marker only *after* every pipeline has been built — the step that
    rejects a bad config.
    """
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state = _docker(
            ["inspect", name, "--format", "{{.State.Running}}|{{.State.ExitCode}}"],
            timeout=30,
        )
        running, _, exit_code = state.stdout.strip().partition("|")
        if running != "true":
            return f"the collector exited with code {exit_code} instead of building the config"

        logs = _docker(["logs", name], timeout=30)
        if READY_MARKER in logs.stdout + logs.stderr:
            return None
        time.sleep(POLL_INTERVAL_SECONDS)

    return f"no readiness line after {STARTUP_TIMEOUT_SECONDS:.0f}s"


def _tail(name: str, lines: int = 25) -> str:
    """Last `lines` of the container's output, for the failure message."""
    logs = _docker(["logs", name], timeout=30)
    combined = (logs.stdout + logs.stderr).splitlines()
    return "\n".join(combined[-lines:])


def test_the_collector_really_builds_the_tracked_config() -> None:
    """The integration half: the collector itself accepts the tracked config.

    Replaces trust in `otelcol validate`, which passes on configs that die at
    startup (module docstring): the graph is built here, and the graph is where
    the rejection happens.
    """
    _require_docker()

    name = f"linkforge-cfg-check-{uuid.uuid4().hex[:8]}"
    started = _docker(
        [
            "run",
            "-d",
            "--name",
            name,
            "-v",
            f"{COLLECTOR_CONFIG}:/etc/otelcol-contrib/config.yaml",
            # The config reads these via ${env:...}; NEW_RELIC_LICENSE_KEY has
            # no default (a missing name is a hard config error), so all of
            # them are supplied exactly as docker-compose.yml supplies them.
            "-e",
            "ENVIRONMENT=development",
            "-e",
            "SERVICE_VERSION=dev",
            "-e",
            "OTLP_HTTP_AUTH_HTPASSWD=linkforge:linkforge",
            "-e",
            "NEW_RELIC_LICENSE_KEY=not-set",
            IMAGE,
            "--config=/etc/otelcol-contrib/config.yaml",
        ],
        timeout=120,
    )
    assert started.returncode == 0, f"docker run failed:\n{started.stderr.strip()}"

    try:
        failure = _wait_until_ready(name)
        logs = "" if failure is None else _tail(name)
    finally:
        # Always remove: a leaked container would keep a rejected config alive
        # to confuse whoever looks at `docker ps` next.
        _docker(["rm", "-f", name], timeout=60)

    assert failure is None, (
        f"{failure} — docker/otel-collector-config.yaml must build its pipeline "
        f'graph (readiness marker: "{READY_MARKER}").\n'
        f"--- collector log (tail) ---\n{logs}"
    )
