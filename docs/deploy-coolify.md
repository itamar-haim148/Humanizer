# Deploying to Coolify

A single Docker Compose application that runs the Humanize API + Web on one VPS.

## Prerequisites

- A Coolify v4 server already provisioned (Caddy proxy, registered domain).
- A Git remote with this repository pushed.

## Step 1 — Create the resource

1. **Projects → New Resource → Docker Compose**.
2. Connect your Git repo and pick the branch (e.g. `main`).
3. Build Pack: **Docker Compose**.
4. Compose file path: `docker-compose.yml` (default).

## Step 2 — Environment variables

Set the following on the Coolify *Environment Variables* tab. All have safe
defaults; override only as needed.

| Name | Default | Notes |
|------|---------|-------|
| `APP_ENV` | `production` | |
| `WEB_ORIGIN` | `https://YOUR-DOMAIN` | Public site URL (CORS allow-list). |
| `NEXT_PUBLIC_API_BASE_URL` | `http://api:8000` | Internal compose DNS; only override if exposing the API publicly. |
| `MAX_TEXT_LENGTH` | `10000` | Per-request char cap. |
| `RATE_LIMIT_PER_MIN` | `30` | Per IP. |
| `TRUST_PROXY` | `true` | Coolify proxy injects `X-Forwarded-For`. |
| `ENABLE_SYNTHID` | `false` | Set to `true` to enable HF Transformers SynthID detector. |
| `SYNTHID_MODEL` | `google/gemma-2b` | Pulled into the `hf_cache` volume on first call. |
| `UVICORN_WORKERS` | `2` | Sized for a 2-vCPU droplet. |
| `WEB_PORT` | `3000` | Coolify maps this to the public port via its proxy. |

## Step 3 — Expose only the web service

The `api` service uses `expose: "8000"` so the port is reachable only within
the `humanize-net` bridge. Coolify routes the public domain to the `web`
service's port 3000. There is no need (and you should not) expose port 8000
publicly.

## Step 4 — Volumes

The named volume `hf_cache` is preserved across rebuilds. This is critical if
`ENABLE_SYNTHID=true` so the multi-GB model download survives container
recreation.

## Step 5 — Domain + TLS

1. In Coolify → *Domains*, attach your domain to the **web** service.
2. Enable **Auto SSL** (Caddy will issue Let's Encrypt).
3. Set Force HTTPS.

## Step 6 — Deploy

Click **Deploy**. Health checks should turn green for both services within
~60s (api ~30s warmup, web ~20s).

## Verifying

- `https://YOUR-DOMAIN/` should render the Humanize/Detect UI.
- The container logs (Coolify viewer) show one JSON line per request with
  `request_id`, `route`, `status`, `latency_ms`.
- `https://YOUR-DOMAIN/api/health` is not exposed by default. To smoke-test the
  API end to end, use the UI (which calls `/api/humanize` and `/api/detect`).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `web` healthcheck fails | API not yet healthy → `web` depends on `api.service_healthy`; check API logs | Wait, or inspect `humanize-api` logs |
| 429 errors during testing | Per-IP rate limit | Bump `RATE_LIMIT_PER_MIN` |
| SynthID always reports `available=false` | `ENABLE_SYNTHID=false` or model not in cache | Set `true`, wait for first cold-start download |
| Hebrew text shows boxes | Font not loaded | Ensure outbound network for `fonts.googleapis.com` from build phase |
