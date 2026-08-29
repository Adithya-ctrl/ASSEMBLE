# ASSEMBLE — Community Systems Compiler

ASSEMBLE tests which initiatives a community can form from declared people, skills, spaces, resources and time. When an initiative is blocked, it explains a solver-confirmed blocking requirement and searches a disclosed finite intervention catalogue for the minimum modelled unlock. A feasible base or verified successor can become an executable Project whose operational assignments, venue, schedule, resources, accessibility and readiness are derived from a fresh solver proof.

The demo fixture is fictional. Results apply only to the declared bounded model and are not predictions of social outcomes.

## Documentation

Start at [`docs/README.md`](docs/README.md). It separates current tutorials, how-to guides, references, and explanations from historical architectural decision records. [`BUILD_STATUS.md`](BUILD_STATUS.md) is the canonical current gate status, and [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) maps requirements to code and evidence.

The numbered current requirements are in [`docs/reference/requirements.md`](docs/reference/requirements.md). Factual presentation materials live under [`docs/presentation/`](docs/presentation/project-overview.md) and remain bounded to the deterministic fictional fixture.

Contributions use [Conventional Commits](docs/how-to/contributing.md#conventional-commits). Documentation, traceability, tests, and current gate evidence must be updated in the same change as behavior.

## Run locally

The canonical guide is [`docs/how-to/run-locally.md`](docs/how-to/run-locally.md). The essential commands are repeated below for convenience.

Start the API from the repository root:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API is then available at `http://127.0.0.1:8000`; its interactive schema is
at `http://127.0.0.1:8000/docs`.

In a second terminal, install and start the interface:

```bash
cd frontend
npm install
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`. The Next.js server forwards same-origin `/api/*`
requests to `ASSEMBLE_API_URL`, so the browser does not need a separate API
configuration. To exercise the production build locally, run:

```bash
cd frontend
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run build
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000
```
