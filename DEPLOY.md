# Deploying DarkWake (free stack)

DarkWake runs as a single always-serving **Docker web service** (FastAPI serving
the REST API, the live WebSocket channels, *and* the built React SPA from one
origin), backed by a **free managed PostGIS** database.

This guide targets a **$0 / no-credit-card** setup:

| Piece | Service | Free tier |
|---|---|---|
| Web service (API + SPA) | [Render](https://render.com) free plan | 512 MB / 0.1 CPU, 750 hrs/mo, spins down after 15 min idle |
| Database (PostGIS) | [Supabase](https://supabase.com) free plan | 500 MB, PostGIS, pauses after 7 days idle |
| Uptime + keep-alive | [UptimeRobot](https://uptimerobot.com) free | 50 monitors, 5-min interval |

> The DB is deliberately **not** Render's own free Postgres — that one deletes
> data after 30 days. Supabase (or Neon) is permanent.

## Architecture in production

```
                    ┌────────────────────────────────────────┐
Browser  ───────►   │  darkwake web service (Render, Docker)  │
(https + wss)       │  ├─ FastAPI REST (/scenarios, /events…) │
                    │  ├─ WebSockets (/ws/live, /ws/timeline) │ ──► Supabase PostGIS
                    │  └─ static React SPA  (/, /assets/*)    │     (Session pooler, 5432)
                    │  background: AISStream feed, SAR poll,  │
                    │              PostGIS persistence loop   │
                    └────────────────────────────────────────┘
        UptimeRobot ──(GET /health every 5 min)──▲ keeps it awake + alerts
```

Serving the SPA from the same origin as the API means the frontend's relative
`fetch()` calls and `wss://<host>/ws/*` connections work with no proxy or CORS
setup.

## Step 1 — Database (Supabase)

1. Create a project at [supabase.com](https://supabase.com) (or reuse one).
2. Enable PostGIS: **Database → Extensions →** search `postgis` → enable. (The
   app's migration also runs `CREATE EXTENSION IF NOT EXISTS postgis`, but
   enabling it here first avoids permission edge cases.)
3. Get the connection string: **Project Settings → Database → Connection string
   → "Session pooler"** (host looks like `aws-0-<region>.pooler.supabase.com`,
   port `5432`). Copy the URI and fill in your DB password.

   Use the **Session pooler** (not the Transaction pooler on 6543, and not the
   direct `db.<ref>.supabase.co` host): Render connects over IPv4 and the app's
   async driver needs prepared-statement support, which the session pooler
   provides.

   It should look like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

## Step 2 — Web service (Render)

1. Push this repo to GitHub/GitLab.
2. In the Render Dashboard: **New → Blueprint**, select this repo. Render reads
   [`render.yaml`](./render.yaml) and creates the `darkwake` free web service.
3. Set the environment variables (all marked `sync: false`):
   - `DATABASE_URL` — the Supabase Session-pooler URI from Step 1
   - `AISSTREAM_API_KEY` — live AIS stream key
   - `GFW_API_TOKEN` — Global Fishing Watch SAR token
   - update `DIGITRAFFIC_USER` to a real contact string
4. Apply. The first deploy builds the image, runs migrations, then starts
   uvicorn. Open the service URL (e.g. `https://darkwake.onrender.com`).

The app boots even before the API keys are set (ingest logs a warning and stays
idle), so you can verify the UI first, then add keys.

## Step 3 — Keep-alive + monitoring (UptimeRobot)

Render's free service sleeps after 15 min of inactivity. A monitor that pings it
every 5 minutes keeps it awake **and** is your monitoring:

1. Create a free [UptimeRobot](https://uptimerobot.com) account.
2. **Add New Monitor → HTTP(s)**, URL `https://<your-host>/status`, interval
   **5 minutes**.
3. Add an alert contact (email) so you're notified if it goes down.
4. Optional: add a **keyword monitor** on the same URL that alerts when the
   response contains `"ais_connected":false` — catches a silently dropped live
   feed while the app itself is still up.

> 750 free instance-hours/month ≈ 31 days, enough to keep one service awake
> 24/7. Don't add a second always-on free service or you'll exceed the cap.

## Monitoring endpoints

| Path | Purpose | Codes |
|---|---|---|
| `/health` | Liveness — Render's health check target. Always `200` if the process is up. | `200` |
| `/ready` | Readiness — checks the DB is reachable. | `200` / `503` |
| `/status` | Rich JSON: `db`, `ais_connected`, `vessel_count`, `sar_detection_count`, `ws_client_count`, `uptime_seconds`. | `200` / `503` |

Render's dashboard also provides deploy/live logs and CPU/memory metrics, plus
native notifications (Settings → Notifications) for failed deploys.

## Swapping the database later

`DATABASE_URL` is the only DB coupling. To move to Neon (or a paid Supabase/RDS),
just point `DATABASE_URL` at the new PostGIS connection string and redeploy — no
code changes. The app normalizes `postgres://`/`postgresql://` schemes
automatically.

## Local production-parity check

Build and run the exact production image locally:

```bash
docker build -t darkwake .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL='postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
  -e AISSTREAM_API_KEY=... -e GFW_API_TOKEN=... \
  darkwake
# → app + UI on http://localhost:8000 ; check /health and /status
```

(`docker compose up` remains the day-to-day dev workflow with hot reload.)
