from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "production-deploy.yml"


def test_production_deploy_workflow_exists_and_is_gated():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_run:" in text
    assert "workflows: [CI]" in text
    assert "types: [completed]" in text
    assert "branches: [main]" in text
    assert "workflow_dispatch:" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "stale" in text.lower()
    assert "cancel-in-progress: false" in text
    assert "RENDER_DEPLOY_HOOK_URL" in text
    assert "RENDER_OTEL_DEPLOY_HOOK_URL" in text
    assert "VERCEL_DEPLOY_HOOK_URL" in text
    assert "linkforge-otel-collector" in text
    assert "/health" in text
    assert "/api/v1/ping" in text
