# Auth and invitation API contract pointer

The executable Builder 2 contract is defined by `backend/app/auth/models.py` for strict request/response models, `backend/app/auth/service.py` for lifecycle and authorisation rules, `backend/app/auth/storage.py` plus `backend/app/auth/migrations.py` for persistent invariants, and `backend/app/auth/api.py` for HTTP routes, cookies and stable error translation.

The canonical human-readable contract is [`../docs/reference/identity-community-invitations.md`](../docs/reference/identity-community-invitations.md). Integration is deliberately separate from `backend/app/main.py`; see [`../docs/how-to/integrate-auth-backend.md`](../docs/how-to/integrate-auth-backend.md). The exact two-hunk control-centre patch is [`auth-main-integration.patch`](auth-main-integration.patch).

Unknown fields are rejected. Errors use the repository envelope:

```json
{"error":{"code":"STABLE_CODE","message":"Human-readable message.","details":{}}}
```

Raw passwords, session tokens, invitation-token digests and invitation tokens after the one-time local delivery response are outside every response schema.
