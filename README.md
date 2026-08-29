# ASSEMBLE — Community Systems Compiler

ASSEMBLE tests which initiatives a community can form from declared people, skills, spaces, resources and time. When an initiative is blocked, it explains a solver-confirmed blocking requirement and searches a disclosed finite intervention catalogue for the minimum modelled unlock. A feasible base or verified successor can become an executable Project whose operational assignments, venue, schedule, resources, accessibility and readiness are derived from a fresh solver proof. The integrated FastAPI backend also provides local accounts, persisted community membership and invitations, plus backend-only structural stress, minimum-disruption recompilation and one-action capability-frontier analyses.

The demo fixture is fictional. Results apply only to the declared bounded model and are not predictions of social outcomes.

## Documentation

Start at [`docs/README.md`](docs/README.md). It separates current tutorials, how-to guides, references, and explanations from historical architectural decision records. [`BUILD_STATUS.md`](BUILD_STATUS.md) is the canonical current gate status, and [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) maps requirements to code and evidence.

The numbered current requirements are in [`docs/reference/requirements.md`](docs/reference/requirements.md). The interface is organised into route-backed Overview, Community, Initiatives, Initiative Proof, Projects, Project Proof, and Preferences areas; the same proof context is preserved during in-app navigation. The current frontend does not expose the backend identity, community-administration, invitation, or structural-resilience APIs: its account control remains disabled, auth-created SQLite communities are not linked to the solver fixture, Projects and proof state remain in memory, and solver, reasoning, Project and M7 routes are deliberately not role-gated. Factual presentation materials live under [`docs/presentation/`](docs/presentation/project-overview.md) and remain bounded to the deterministic fictional fixture.

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
at `http://127.0.0.1:8000/docs`. Unless `ASSEMBLE_AUTH_DB_PATH` is set, local
identity state is stored in `backend/.data/auth.sqlite3`. On POSIX the auth
directory and database runtime files are restricted to modes `0700` and `0600`
respectively; unsafe existing permissions fail closed.

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
