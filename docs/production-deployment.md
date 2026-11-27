# Production Deployment (LinkForge / url-shortner)

This repo uses a CI-gated production deploy for `main`.

## Flow

1. Push/merge to `main` runs `.github/workflows/ci.yml`.
2. If CI completes successfully, `.github/workflows/production-deploy.yml` runs via `workflow_run`.
3. The deploy workflow resolves the current `main` tip and skips stale CI runs.
4. It triggers Render and Vercel deploy hooks (GitHub secrets only).
5. It runs a post-deploy smoke probe against the deployed backend.

A red or cancelled CI run does not deploy.

## Required GitHub Secrets

Add under **Settings -> Secrets and variables -> Actions**:

- `RENDER_DEPLOY_HOOK_URL` - Render deploy hook for `linkforge-backend`.
- `VERCEL_DEPLOY_HOOK_URL` - Vercel deploy hook for the frontend production/main deployment.

Optional but recommended:

- `RENDER_OTEL_DEPLOY_HOOK_URL` - Render deploy hook for `linkforge-otel-collector`. If unset, the deploy workflow skips collector with a warning.

Optional:

- Repository variable `SMOKE_BASE_URL` - defaults to `https://linkforge-backend-v46v.onrender.com`.

## Render Setup

1. Confirm the backend service type in Render dashboard.
   - `backend/render.yaml` currently describes a **source-based Python** service.
   - CI also publishes GHCR images (`backend:${sha}`, `backend:latest`) after green main CI.
2. Disable **Auto Deploy on push** for production services you want gated.
3. Create a Deploy Hook for `linkforge-backend` and store it as `RENDER_DEPLOY_HOOK_URL`.
4. Create a Deploy Hook for `linkforge-otel-collector` and store it as `RENDER_OTEL_DEPLOY_HOOK_URL` (recommended for full Render parity; workflow skips with warning if unset).
5. If the service is **source/Git-backed**, the workflow appends `ref=<validated SHA>` to the hook request. Both Render services in `backend/render.yaml` are currently source/Docker-backed on Render.
6. If a service becomes **image-backed**, update the workflow to pass `imgURL=<immutable image>` (prefer SHA/digest, not `latest`).

## Vercel Setup

1. Disable Git auto-deploy for production/main, or rely on `frontend/vercel.json`:
   ```json
   { "git": { "deploymentEnabled": false } }
   ```
2. Create a Vercel Deploy Hook for `main`.
3. Store it as `VERCEL_DEPLOY_HOOK_URL`.

## GitHub Setup

- Require `CI` checks in branch protection for `main`.
- Keep deploy hooks in GitHub Secrets only; never commit them.
- Optionally use a `production` environment with required reviewers.

## Manual Redeploy / Rollback

- Use **Actions -> Deploy production -> Run workflow** to redeploy the current `main` tip after a transient hook failure.
- For rollback, redeploy a previously known-good commit/image through the platform, or revert on `main` and let the gated flow deploy the reverted SHA after CI passes.
- Prefer immutable SHA/digest artifacts for rollback certainty.

## Verification

After setup:

1. Trigger `Deploy production` manually (`workflow_dispatch`) and confirm both hooks return 2xx.
2. Confirm smoke passes (`/health`, `/api/v1/ping`).
3. Push a commit to `main`: CI green should trigger deploy; CI red/cancelled should not.
4. Confirm Render/Vercel auto-deploy-on-push is disabled.
