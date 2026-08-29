# Contribute safely

## Before changing code

1. Read [`../README.md`](../README.md) to find the canonical page for the behavior.
2. Read [`../../BUILD_STATUS.md`](../../BUILD_STATUS.md) for current blockers and intentionally absent scope.
3. Read only the ADRs relevant to the change.
4. Verify the current implementation and tests; documentation is evidence and navigation, not executable authority.
5. Read [`audit-documentation.md`](audit-documentation.md) before declaring a milestone complete.

The event execution packet remains the product authority. Do not silently add authentication, generic project management, cloud services, deployment, publication, or submission behavior.

## Change rule

Every behavior change must include:

- implementation and regression tests;
- the current-state reference or how-to page affected by the change;
- an updated row in [`../TRACEABILITY.md`](../TRACEABILITY.md);
- current cumulative gate evidence in [`../../BUILD_STATUS.md`](../../BUILD_STATUS.md);
- an ADR only when the change makes a durable architectural decision or supersedes one.

Keep these implementation, test, documentation, traceability, and status updates in the same change.

Documentation drift is a hard gate. A milestone must not be accepted, committed, or pushed while either the automated audit or human semantic replay in [`audit-documentation.md`](audit-documentation.md) is incomplete or failing.

Do not add routine implementation history to tutorials, how-to guides, reference pages, explanations, README, or build status. Git records routine change history.

## Conventional Commits

Use this form for every authorised commit:

```text
<type>(<scope>): <imperative summary>
```

Allowed types:

- `feat`: user-visible capability;
- `fix`: defect repair;
- `docs`: documentation-only change;
- `test`: test-only change;
- `refactor`: behavior-preserving structure change;
- `perf`: measured performance improvement;
- `build`: dependency or build-system change;
- `ci`: continuous-integration change;
- `chore`: repository maintenance that fits no other type;
- `revert`: an explicit reversal.

Preferred scopes are `backend`, `frontend`, `solver`, `reasoning`, `project`, `accessibility`, `security`, and `docs`. Keep each commit single-purpose. Use a body when the summary cannot state the trust boundary, migration, or verification evidence. Mark breaking changes with `!` and a `BREAKING CHANGE:` footer.

Examples:

```text
feat(project): create projects from verified solver plans
fix(security): reject forged base community states
docs(docs): add current API and accessibility references
```

Writing a Conventional Commit does not itself authorise committing, pushing, publishing, deploying, or submitting.

Create a local Conventional Commit only at an accepted milestone after the required cumulative code, documentation, and browser gates pass. Do not checkpoint arbitrary broken intermediate edits. The private `origin` and accepted remote checkpoints already exist; preserve them, do not rewrite history, and do not push another commit until explicit judge-sharing authority is given. ADRs record durable architectural decisions, Git commits record accepted iterations, and `BUILD_STATUS.md` records only current health.

## Security and privacy

- Never place credentials, session material, private payloads, or raw sensitive logs in code, fixtures, tests, documentation, or commits.
- Treat all client fields as untrusted and validate at the backend boundary.
- Derive feasibility, assignments, status, readiness, venue, time, and resources from authoritative data and the solver.
- Fail closed when state provenance, references, or proof completeness cannot be established.

## Completion

Run [`verify-changes.md`](verify-changes.md). A focused test is not cumulative acceptance. Do not describe work as accepted until the designated manager independently replays the required gates.
