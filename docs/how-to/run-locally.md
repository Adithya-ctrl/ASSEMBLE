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

The installed auth router uses `backend/.data/auth.sqlite3` by default. Override it with an explicit persistent path when you need a separate local identity store:

```bash
ASSEMBLE_AUTH_DB_PATH=/absolute/private/path/auth.sqlite3 PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On POSIX, the database parent directory must be mode `0700` and the database, WAL and SHM files must be mode `0600`; the store creates new paths with those modes and rejects unsafe existing permissions. Set `ASSEMBLE_AUTH_COOKIE_SECURE=1` only when the browser boundary is HTTPS.

The exact browser-origin allow-list defaults to `http://localhost:3000,http://127.0.0.1:3000`. If the frontend uses another port, set a canonical comma-separated list with `ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS`; entries must be exact HTTP(S) origins with no path or trailing slash. Invalid or oversized configuration stops auth installation.

## Interface

In another terminal:

```bash
cd frontend
npm install
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`. Browser calls remain same-origin; the Next.js server forwards `/api/*` to `ASSEMBLE_API_URL`.

The current interface does not expose signup, login, community administration, invitations, stress testing, recompilation or the capability frontier. Its account control remains disabled. Use the API/OpenAPI surface for backend replay; do not describe the interface as demonstrating those capabilities.

## Production-like interface

```bash
cd frontend
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run build
ASSEMBLE_API_URL=http://127.0.0.1:8000 npm run start -- --hostname 127.0.0.1 --port 3000
```

The core and local identity store work without an OpenAI API key, cloud subscription, OAuth provider, external authentication service or email provider. Auth/community/invitation records persist in SQLite; Projects and proof state remain in memory.
