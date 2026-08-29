# ADR 0004: Living documentation and Conventional Commits

- Status: Accepted
- Date: 2026-08-29

## Context

Event-day implementation changed quickly, and status notes had already fallen behind the cumulative test count and current Project behavior. Mixing current behavior with old plans would make judges and future builders unable to identify the truth.

## Decision

Organize current documentation by Diátaxis reader intent. Assign README/docs index as the map, contributing guidance as the constitution, BUILD_STATUS as current status, and ADRs as history. Current pages describe only current behavior. Update documentation and traceability in the same change as behavior.

Use local Conventional Commits for accepted milestone checkpoints after cumulative code, documentation, and browser gates pass. Do not commit broken intermediate edits. Preserve the existing private origin and remote history; a local commit does not authorise a push.

## Consequences

- Superseded behavior appears only in an ADR that records the replacement.
- Routine implementation history remains in Git rather than current docs.
- A change is incomplete when its canonical documentation or verification evidence is stale.
- Commit formatting does not grant push authority.
- Accepted iterations live in Git; current health remains in BUILD_STATUS rather than accumulating there as history.
