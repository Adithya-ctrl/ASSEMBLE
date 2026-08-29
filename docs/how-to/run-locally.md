# Run ASSEMBLE locally

## API

From the repository root:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/pytest -q
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API is available at `http://127.0.0.1:8000`. OpenAPI is available at `http://127.0.0.1:8000/docs`.

## Interface

In another terminal:

```bash
cd frontend
npm install
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`. Browser calls remain same-origin; the Next.js server forwards `/api/*` to `ASSEMBLE_API_URL`.

## Production-like interface

```bash
cd frontend
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run build
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000
```

The core is designed to work locally without an OpenAI API key, cloud subscription, OAuth provider, or external authentication service.
