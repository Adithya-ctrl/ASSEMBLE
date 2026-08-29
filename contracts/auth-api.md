# Auth and invitation API contract pointer

The executable integrated contract is defined by `backend/app/auth/models.py` for strict request/response models, `backend/app/auth/service.py` for lifecycle and authorisation rules, `backend/app/auth/storage.py` plus `backend/app/auth/migrations.py` for persistent invariants, `backend/app/auth/api.py` for HTTP routes, cookies and stable error translation, and the registration call in `backend/app/main.py`.

The canonical human-readable contract is [`../docs/reference/identity-community-invitations.md`](../docs/reference/identity-community-invitations.md). The current installation and local persistence boundary are documented in [`../docs/how-to/integrate-auth-backend.md`](../docs/how-to/integrate-auth-backend.md). [`auth-main-integration.patch`](auth-main-integration.patch) is retained as the historical review artifact for the already-applied two-point installation; it is not a future integration instruction.

Unknown fields are rejected. Errors use the repository envelope:

```json
{"error":{"code":"STABLE_CODE","message":"Human-readable message.","details":{}}}
```

Raw passwords, session tokens, invitation-token digests and invitation tokens after the one-time local delivery response are outside every response schema.

The auth permission matrix applies to auth and community-administration routes only. Solver, reasoning, Project, stress-test, recompile and frontier routes are deliberately not role-gated. The same-origin frontend now provides signup, login, session, logout, profile, password, Settings, persisted collaboration-space, membership, invitation and Administrator-audit workflows. It consumes the strict response contract without reading or storing the HttpOnly session token. These collaboration surfaces remain separate from the planning fixture and do not turn community roles into solver, Project or M7 permissions.

`ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS` is an exact bounded canonical HTTP(S) origin allow-list; it is never inferred or broadened from Host or forwarded headers. Auth middleware namespace matching is segment-aware, so similarly named non-auth routes retain the ordinary application 404 boundary. Auth-created SQLite communities are not linked to the authoritative solver fixture.
