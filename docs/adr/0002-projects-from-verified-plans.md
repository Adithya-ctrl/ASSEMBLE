# ADR 0002: Projects from verified plans

- Status: Accepted
- Date: 2026-08-29

## Context

The solver could prove that an initiative was feasible, but the application did not yet turn that proof into a delivery-ready object. A disconnected project-management layer would have duplicated assignments and allowed client-authored readiness claims.

## Decision

Create a Project only by starting from authoritative S0, replaying an explicit 0–2 action path, and solving the target again. Derive operational assignments, venue, schedule, resources, language capacity, accessibility, and readiness from the resulting witness. Bind source-plan identity to canonical state content and path; bind Project identity additionally to normalized editable metadata.

Reject a non-authoritative base, an incomplete path, INFEASIBLE, or UNKNOWN without returning a Project.

## Consequences

- Basic Workshop uses an explicit empty path.
- Multilingual Clinic requires successor verification in the UI and authoritative replay at creation.
- The client cannot choose Project status, readiness, assignments, or allocations.
- Generic CRUD, tasks, authentication, and project-level roles remain separate future decisions.
