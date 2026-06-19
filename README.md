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

## Local development (without Docker)

1. Create and activate a Python virtual environment:

```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Windows (cmd)
.\.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set required values (at minimum `GEMINI_API_KEY`, `DATABASE_URL`, and `REDIS_URL`).

4. Start PostgreSQL and Redis. Easiest option is to use Docker Compose from the repository root:

```bash
docker compose up -d db redis
```

5. Start the API (reload enabled for development):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. Start a Celery worker in a separate terminal:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

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

## Example curl requests

- Upload a CSV file (creates a new job):

```bash
curl -X POST "http://localhost:8000/jobs/upload" \
	-H "accept: application/json" \
	-F "file=@data/transactions.csv;type=text/csv"
```

- Check job status:

```bash
curl -s "http://localhost:8000/jobs/1/status" | jq
```

- Download job results (only when status is `completed`):

```bash
curl -s "http://localhost:8000/jobs/1/results" | jq
```

- List recent jobs (optionally filter by status):

```bash
curl "http://localhost:8000/jobs?status=completed" | jq
```

Additional example curl requests:

- Upload a CSV (returns `job_id`):

```bash
curl -X POST "http://localhost:8000/jobs/upload" \
	-H "accept: application/json" \
	-F "file=@data/transactions.csv;type=text/csv"
```

- Check job status (replace `1` with your `job_id`):

```bash
curl -s "http://localhost:8000/jobs/1/status" | jq '.'
```

- Fetch results once job is `completed`:

```bash
curl -s "http://localhost:8000/jobs/1/results" | jq '.'
```

- List jobs, optionally filter by status:

```bash
curl "http://localhost:8000/jobs?status=completed"
```

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
