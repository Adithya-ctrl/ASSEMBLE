# ADR 0003: Equivalent graph and list views

- Status: Accepted
- Date: 2026-08-29

## Context

The civic planning canvas benefits from a spatial representation, but connection lines alone are not sufficient for keyboard, assistive-technology, reduced-motion, narrow-screen, or zoomed use.

## Decision

Provide labelled Graph View and List View controls. Both render from the same community state and expose equivalent organisation, person, space, resource, identity, capability, language, availability, capacity, quantity, and feature facts. SVG seams remain decorative.

## Consequences

- Visual relationships never become the only evidence source.
- Parity is a browser acceptance condition.
- Both views must be updated together when community facts change.
