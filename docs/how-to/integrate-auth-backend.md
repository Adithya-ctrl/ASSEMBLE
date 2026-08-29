# Inspect and configure the integrated auth backend

The shared FastAPI application already registers the auth router with one import and one call after the application, middleware and existing routes are created:

```python
from app.auth.api import install_auth_api

install_auth_api(app)
```

[`../../contracts/auth-main-integration.patch`](../../contracts/auth-main-integration.patch) records the reviewed two-hunk installation. Do not apply it again: the import and registration call are present in `backend/app/main.py`, with no existing route-body change.

`install_auth_api` reads `ASSEMBLE_AUTH_DB_PATH` and `ASSEMBLE_AUTH_COOKIE_SECURE`. With no path override it uses `backend/.data/auth.sqlite3`; `backend/.data/` is ignored by Git. For a repeatable local run, use that default or set the path to a dedicated persistent writable file. On POSIX, the store creates the parent directory with mode `0700` and the database, WAL and SHM files with mode `0600`; startup fails closed if an existing path grants group or other access. Leave secure cookies disabled only for localhost HTTP. Set `ASSEMBLE_AUTH_COOKIE_SECURE=1` behind HTTPS.

`ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS` is a comma-separated exact allow-list of canonical serialized HTTP(S) origins with no path or trailing slash. It defaults to `http://localhost:3000,http://127.0.0.1:3000`; set it explicitly for another browser-proxy port, such as `http://localhost:4173`. The setting accepts at most 32 unique entries and 4096 UTF-8 bytes. Empty, wildcard, credential-bearing, malformed, non-canonical, oversized, path/query/fragment-bearing or otherwise ambiguous values fail installation closed. A request `Origin` must equal one configured entry exactly. `Host`, `X-Forwarded-Host` and other forwarded headers never broaden the list.

The installed auth-scoped boundary counts actual request bytes, requires JSON for unsafe routes, ignores `X-Forwarded-For`, and checks present browser `Origin` and `Sec-Fetch-Site` headers against the explicit local origin contract. Do not deploy it behind a proxy that rewrites client or origin identity without a separate trusted-proxy review.

Auth namespace matching is segment-aware. Lookalike routes such as `/api/authentic`, `/api/communities-v2` and `/api/invitations-old` fall through to the ordinary application 404 boundary; they do not inherit auth middleware behavior.

The existing Next.js same-origin proxy is the intended future browser boundary. The current frontend has no signup, login, profile, community, membership or invitation workflow and its account control remains disabled. If a later frontend calls FastAPI cross-origin and sends cookies directly, review CORS origin, credentials and headers separately.

Auth and community-administration routes enforce sessions and persisted community roles. Auth-created SQLite communities are not linked to the solver's authoritative fictional fixture. The existing solver, reasoning, Project, stress-test, recompile and frontier routes are deliberately not role-gated. Do not infer Project persistence or Project membership from auth persistence.

Run the focused auth suite and complete backend suite with a private temporary `ASSEMBLE_AUTH_DB_PATH`, then restart the application against one dedicated persistent file and replay signup → community → invitation → accept → role check. The current integrated checkpoint is `63 passed` for `backend/tests/auth` and `257 passed` for `backend/tests`; the only warning is the already-present Starlette `httpx` TestClient deprecation. These are backend integration gates, not frontend availability or public-deployment acceptance.
