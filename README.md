# Financial Transaction Processor

Lightweight FastAPI service that ingests a CSV of transactions, processes rows via Celery, enriches data with an LLM, and persists results in PostgreSQL.

## Stack

- FastAPI (API)
- Celery (worker)
- PostgreSQL (db)
- Redis (broker/backend)
- Gemini (LLM) — configured via environment
- Docker & Docker Compose

## Quick start

1. Copy `.env.example` to `.env` and set required values (at minimum `GEMINI_API_KEY` when using Gemini).

2. Build and start the full stack from the repository root:

```bash
docker compose up --build
```

3. Open the API docs at: `http://localhost:8000/docs`

## Important env vars

- `GEMINI_API_KEY` — (optional) API key for Gemini/Google GenAI
- `GEMINI_MODEL` — model name (defaults set in `.env`/settings)
- `DATABASE_URL` & `REDIS_URL` — set by compose by default
- `UPLOAD_DIR` — where uploaded CSVs are stored (`/app/storage/uploads` inside container)
- `RESULT_DIR` — where results are written (`/app/storage/results` inside container)

## API endpoints

- `POST /jobs/upload` — multipart/form-data, field `file` (CSV). Returns `{job_id, status}`. Example curl:

```bash
curl -X POST "http://localhost:8000/jobs/upload" -H "accept: application/json" -F "file=@transactions.csv;type=text/csv"
```

- `GET /jobs/{job_id}/status` — returns job lifecycle status and error message if failed.
- `GET /jobs/{job_id}/results` — returns transactions, anomalies and summary (only when status is `completed`).
- `GET /jobs` — list recent jobs.

## Verify & debug

- Check running containers and ports:

```bash
docker compose ps
```

- Stream logs (all services):

```bash
docker compose logs -f
```

- Stream worker logs only:

```bash
docker compose logs -f worker
```

- Quick DB checks (from host; requires compose network access):

```bash
docker compose exec db psql -U postgres -d transactions -c "SELECT COUNT(*) FROM jobs;"
```

## Reset application state (start fresh)

- Truncate tables and reset IDs (recommended for testing):

```bash
docker compose exec -T db psql -U postgres -d transactions -c "TRUNCATE TABLE job_summaries, transactions, jobs RESTART IDENTITY CASCADE;"
Remove-Item -Recurse -Force .\storage\uploads\* ; Remove-Item -Recurse -Force .\storage\results\*   # PowerShell host
```

- Or remove volumes (destroys DB data):

```bash
docker compose down -v
```

## Known troubleshooting

- Date parsing errors: parser supports `DD-MM-YYYY`, `YYYY/MM/DD`, and `YYYY-MM-DD`.
- JSON serialization errors: task payloads are normalized to ISO strings for `date`/`datetime` before DB writes.
- If you change Python code, rebuild images and restart:

```bash
docker compose up -d --build
```

## Notes

- Uploaded CSVs are stored under the `storage/uploads` folder in the repository (mounted into the containers).
- Results are written to `storage/results`.
- The app will create DB tables on startup if they do not exist.

If you want, I can also add a short example of how to query `/jobs/{job_id}/status` and a sample `curl` for `results`.
