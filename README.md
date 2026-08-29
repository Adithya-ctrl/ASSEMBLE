# ASSEMBLE — Community Systems Compiler

ASSEMBLE tests which initiatives a community can form from declared people, skills, spaces, resources and time. When an initiative is blocked, it explains a solver-confirmed blocking requirement and searches a disclosed finite intervention catalogue for the minimum modelled unlock. A feasible base or verified successor can become an executable Project whose operational assignments, venue, schedule, resources, accessibility and readiness are derived from a fresh solver proof. The integrated local product also provides accounts, persisted community membership and invitations, plus a Resilience Lab for structural stress, minimum-disruption recovery and one-action capability-frontier analysis.

The demo fixture is fictional. Results apply only to the declared bounded model and are not predictions of social outcomes.

## Documentation

Start at [`docs/README.md`](docs/README.md). It separates current tutorials, how-to guides, references, and explanations from historical architectural decision records. [`BUILD_STATUS.md`](BUILD_STATUS.md) is the canonical current gate status, and [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) maps requirements to code and evidence.

The numbered current requirements are in [`docs/reference/requirements.md`](docs/reference/requirements.md). The interface is organised into route-backed planning, Project, Resilience, Settings, identity, and Collaboration areas; the same proof context is preserved during in-app planning navigation. Its Civic Toybox presentation uses five original compressed WebP scenes plus isolated CSS perspective and pointer parallax, with static mobile and reduced-motion fallbacks and no WebGL dependency. The frontend provides local signup/login/session/profile/password controls and persisted collaboration-space administration, while keeping those SQLite spaces explicitly separate from the fictional solver fixture. The Resilience Lab reconstructs only authoritative S0 or a verified catalyst path and keeps its counterfactual receipts outside operational Project lineage. Projects and proof state remain in memory, and community roles deliberately do not gate solver, reasoning, Project, or M7 routes. Factual presentation materials live under [`docs/presentation/`](docs/presentation/project-overview.md) and remain bounded to the deterministic fictional fixture.

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
