# CIVITWIN AI

A local-first planning sandbox for the KPITB AI Innovation Challenge. The first demonstration uses fictional communities and weekly outpatient-service assumptions in a schematic representation of Bajaur. Mohmand and Khyber are future expansion districts.

The [software requirements specification](docs/SRS.md) defines the workflow and acceptance gates. The [implementation status](docs/IMPLEMENTATION_STATUS.md) records the commands run and which gates have passed.

## Foundation setup

Use Python 3.11–3.13, uv, and Node.js 22.12 or later. Run these from the repository root in PowerShell:

```powershell
uv sync --locked
uv run --locked python scripts/seed.py --check
uv run --locked pytest
uv run --locked ruff check .
uv run --locked mypy
npm ci
npm run lint:web
npm run typecheck:web
npm run test:web
```

The seed command `uv run --locked python scripts/seed.py` regenerates the synthetic dataset, disconnected test fixture and machine-readable schemas. The demo uses visits per modeled week, integer travel minutes, and weekly-equivalent Pakistani rupees. Fictional service sites and schematic positions do not describe real operations.

## Run the local planner

From the repository root, start the API in one terminal:

```powershell
uv run --locked uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000
```

Once `http://127.0.0.1:8000/api/v1/ready` returns `ready`, start the web app in another terminal:

```powershell
npm run dev:web
```

Open [CIVITWIN AI](http://127.0.0.1:3000). Inspect the synthetic dataset, review and confirm a scenario, then run the modeled baseline and optimized plan in sequence. The comparison and report link to the saved runs. Use the report controls to download JSON or CSV or print a copy.

The API applies the Alembic migration and publishes the synthetic seed idempotently at startup. By default SQLite stores the history in `data/civitwin.db`. A schema upgrade creates a consistent SQLite backup before migrating an existing nonempty file. Stop the API before restoring a backup into the configured DB path. To start a fresh demo while retaining history, set `DATABASE_URL` to a new workspace path and restart the API.

Run the isolated browser tests with `npx playwright install chromium` followed by `npm run e2e`. On this Windows workspace, `uv run --locked pytest --basetemp .pytest_cache/local-tests` uses a writable test database directory.

## Optional natural-language planning

The default workflow uses the form, CP-SAT, the independent audit, and offline evidence templates. To enable a provider you have chosen and authorized, copy `.env.example` to a local `.env` and set `AI_ENABLED=true`, `LLM_ENDPOINT` to its complete chat-completions URL, and `LLM_MODEL` to a documented model that accepts strict JSON Schema output. Set `LLM_API_KEY` only if the configured provider requires it. The endpoint accepts HTTPS or HTTP on loopback. Restart the API after changing configuration.

The optional parser accepts bounded synthetic planning requests in English and offers experimental Urdu and Pashto input. Local fixtures exercise the schema and screening. Live provider quality and native-speaker translation review are pending. The parser returns suggested form values, which the planner applies, reviews, and confirms separately. The report can request alternate wording using a constrained list of claims. If the provider is unavailable, the report keeps the deterministic explanation and the form remains available.

Provider calls occur after the planner explicitly requests a draft or alternate wording. With an external endpoint, that sends the allowed prompt or a reduced synthetic evidence packet to the configured service and may incur provider charges. The API key stays in server configuration.
