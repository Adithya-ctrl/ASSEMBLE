# Integrate the isolated auth backend

Builder 2 does not modify `backend/app/main.py`. After reviewing and accepting the isolated slice, the control centre can register it with one import and one call after the FastAPI application and middleware are created:

```python
from app.auth.api import install_auth_api

install_auth_api(app)
```

The directly applicable two-hunk patch is [`../../contracts/auth-main-integration.patch`](../../contracts/auth-main-integration.patch). Apply it only after integrating Builder 2's auth paths; it imports the registration function and invokes it at the end of the existing route module. No existing route body changes.

`install_auth_api` reads `ASSEMBLE_AUTH_DB_PATH` and `ASSEMBLE_AUTH_COOKIE_SECURE`. For a repeatable local run, set the database path to a persistent writable file. Leave secure cookies disabled only for localhost HTTP. Set `ASSEMBLE_AUTH_COOKIE_SECURE=1` behind HTTPS.

The installed auth-scoped boundary counts actual request bytes, requires JSON for unsafe routes, ignores `X-Forwarded-For`, and checks present browser `Origin` and `Sec-Fetch-Site` headers against the explicit local origin contract. Do not deploy it behind a proxy that rewrites client or origin identity without a separate trusted-proxy review.

The existing Next.js same-origin proxy is the intended browser boundary. If a later frontend calls FastAPI cross-origin and sends cookies directly, the control centre must separately review the CORS origin, credentials and header policy; Builder 2 does not change that protected integration surface.

After registration, run the focused auth suite, the complete backend suite, restart the application against the same database file, and replay signup → community → invitation → accept → role check. Do not claim frontend availability until Builder 1 supplies and independently replays the product UI.

Builder 2's latest isolated evidence is `63 passed` for `backend/tests/auth` and `207 passed` for `backend/tests`. The only warning is the already-present Starlette `httpx` TestClient deprecation. Rerun these gates after the control centre applies the patch; counts are evidence from this branch, not a substitute for the control centre's integrated replay.
