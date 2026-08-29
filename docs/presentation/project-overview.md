# ASSEMBLE project overview

## Problem

Community capacity is often distributed across organisations, people, languages, time, accessible spaces, and shared equipment. A promising initiative can still be blocked because those pieces do not line up, while a plausible-looking intervention may address the wrong shortage.

## Audience

The current software is designed to demonstrate value for community coordinators and coalition planners. Initiative participants, community members, technical reviewers, accessibility reviewers, and hackathon judges are stakeholders in the clarity and trustworthiness of the result.

## Purpose

ASSEMBLE makes a declared capacity model inspectable, determines whether a selected initiative is feasible, explains a blocker with factual evidence, compares a finite set of interventions, verifies an immutable successor state, and derives a Project only from a fresh feasible proof.

## What it does now

1. Loads one deterministic fictional community fixture.
2. Separates Community capacity into Overview, People, Places, and Resources, with equivalent graph and list representations and focused detail.
3. Uses dedicated Initiatives and Initiative Proof areas to compile and solve Basic Workshop or Multilingual Clinic with local CP-SAT.
4. Explains Clinic's digital-support shortfall: three required, one available, shortfall two.
5. Finds the lowest-cost sufficient disclosed catalyst: train two existing helpers at cost 2.
6. Applies that action to a copied state, preserves S0, and requires a new solve.
7. Creates a READY Project only after server-side replay and another feasible result.
8. Exposes operational assignments, venue, time, resources, readiness, and a dedicated Project Proof route; exact solver/state internals remain discoverable through Judge Proof Mode and the Technical Inspector.

## Truthful workflow

```text
declared S0 -> compile and solve -> explain blocker -> compare bounded actions
            -> immutable successor -> verify successor -> replay and derive Project
```

The interface does not treat a transition as proof. The Clinic remains blocked until the returned successor is verified, and Project creation solves the authoritative path again.

## Differentiator

ASSEMBLE is neither a chat response nor generic project-management CRUD. Its differentiator is an inspectable chain from declared capacity, through solver-confirmed feasibility and minimum disclosed intervention, to server-derived execution details. Every important status has adjacent evidence or a direct path to the Technical Inspector.

## Current scope and limits

This is localhost hackathon software operating on one small fictional fixture and a finite action catalogue. It has no real-user validation, measured community impact, authentication, RBAC, persistence, tasks, project membership, notifications, external data ingestion, external LLM dependency, cloud deployment, or production claim. The minimum is bounded to the disclosed catalogue and planner limits; it is not a global recommendation over all real-world actions.

## One-sentence value proposition

Within a declared bounded community model, ASSEMBLE turns scattered capacity and a blocked initiative into an inspectable, solver-verified execution plan without inventing evidence.

See the exact requirements in [`../reference/requirements.md`](../reference/requirements.md) and the evidence boundaries in [`../reference/security-validation.md`](../reference/security-validation.md).
