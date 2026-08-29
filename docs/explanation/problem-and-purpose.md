# Problem, purpose, and value

## Concrete problem

Community organisations may collectively have people, skills, languages, spaces, equipment, and available time, yet still struggle to determine whether a proposed initiative can actually run. Capacity is distributed across organisations, dependencies interact, and an apparently useful intervention may repair the wrong constraint.

For example, the current fixture’s Multilingual Digital Help Clinic needs three digital helpers and one Arabic-language support role at a shared accessible venue with laptops and a two-slot window. S0 has only one digital helper. Borrowing more laptops does not repair that shortfall.

## Current software purpose

ASSEMBLE compiles a declared fictional community state into a bounded CP-SAT model and answers:

1. Which declared initiatives have a complete feasible assignment?
2. Which solver-confirmed requirement facts block an initiative?
3. Which minimum intervention in the disclosed catalogue restores feasibility?
4. Does applying that intervention produce a successor state that independently verifies?
5. Can the verified plan be converted into an executable Project with derived people, venue, time, resources, accessibility, languages, and readiness evidence?

## Current value proposition

ASSEMBLE replaces coordination guesswork inside its declared model with an inspectable proof chain. It shows the assignment behind a feasible claim, the facts behind a blocker, the cost and sufficiency of an intervention, the immutable state change, and the fresh proof behind a Project. This lets a coordinator compare modelled options without treating the cheapest action as automatically valid.

## Boundaries on the claim

The current software operates only on the deterministic fictional fixture and submitted bounded models. It does not predict social outcomes, discover real community data, guarantee delivery, measure real-world impact, or prove that its catalogue contains every possible intervention. It has no persistence, authentication, project membership, tasks, deployment, external LLM, or data export.

## Target users and stakeholders

### Community coordinator — primary user

Needs to understand available capacity, test an initiative, see why it is blocked, compare a bounded intervention, and leave with an operationally explicit Project.

Primary jobs:

- inventory declared people, organisations, spaces, resources, capabilities, languages, and time;
- decide whether a specific initiative is feasible now;
- identify a factual shortfall rather than a generic warning;
- choose the least-cost sufficient intervention in the disclosed catalogue;
- inspect the people and assets committed to the resulting plan.

### Coalition planner — planning stakeholder

Needs to understand which organisations contribute capacity and how a catalyst changes the shared state without mutating the original.

### Community member — represented stakeholder

Needs capability, language, availability, and organisational facts to be represented truthfully and not inferred beyond the declared fixture.

### Initiative participant — outcome stakeholder

Needs the plan to expose venue accessibility, capacity, time, language support, resources, and operational roles before delivery is claimed ready.

### Technical reviewer or event judge — assurance stakeholder

Needs to replay the complete journey, inspect solver and state evidence, distinguish demonstrated facts from pitch claims, and confirm accessibility and failure behavior.

## Primary jobs-to-be-done

| Situation | Job | Current evidence of completion |
| --- | --- | --- |
| Capacity is distributed | See one coherent inventory | Equivalent graph and list views |
| An initiative appears plausible | Test exact feasibility | Solver status, assignment, objective, and trace |
| The initiative is blocked | Understand the smallest factual blocker | Required, available, shortfall, source facts, solver-run count |
| Several actions are possible | Find a sufficient minimum | Disclosed catalogue comparison and total cost |
| A catalyst is selected | Preserve provenance | Immutable successor ID, parent ID, and machine-readable diff |
| A successor looks feasible | Prove it independently | Separate verification response |
| A plan is proved | Make execution explicit | Server-derived Project and source-proof control |
