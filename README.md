# ASSEMBLE — Community Systems Compiler

ASSEMBLE tests which initiatives a community can form from declared people, skills, spaces, resources and time. When an initiative is blocked, it explains a solver-confirmed blocking requirement and searches a disclosed finite intervention catalogue for the minimum modelled unlock.

This repository began during the official SYNCS HACK 2026 build window. The demo fixture is fictional. Results apply only to the declared bounded model and are not predictions of social outcomes.

## Run locally

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
