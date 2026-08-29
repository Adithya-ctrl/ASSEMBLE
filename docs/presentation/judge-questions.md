# Judge questions and evidence answers

Use the direct answer first. Offer the deeper answer only if invited, show the named evidence, and finish with the honest boundary. Never substitute an aspirational claim for current behavior.

## Friendly questions

### What problem are you solving, and why does it matter?

- **Direct:** Community capacity is distributed across people, language, time, spaces, equipment, and organisations. ASSEMBLE shows whether those pieces can support a declared initiative and what bounded intervention repairs a proven gap.
- **Deeper:** The current demonstration separates “we seem to have resources” from a complete assignment satisfying all encoded requirements.
- **Evidence to show:** S0 inventory, Basic witness, Clinic digital-support shortfall.
- **Honest boundary:** The pain is plausible and concrete, but this build has not been validated with real community users or impact data.

### Who is it for?

- **Direct:** The demonstrated jobs belong to community coordinators and coalition planners; members, participants, and reviewers need the evidence to remain understandable and auditable.
- **Deeper:** The interface prioritizes a guided capacity-to-Project workflow rather than a generic administration dashboard.
- **Evidence to show:** focused Community categories/detail, labelled Initiative Proof actions, Project detail, and Project Proof.
- **Honest boundary:** There are no accounts, project roles, or multi-user workflows in the current build.

### What is novel about ASSEMBLE, and how does it fit the theme?

- **Direct:** It connects civic capacity coordination to a verifiable chain: model, solve, explain, minimum disclosed intervention, immutable successor, fresh verification, and derived Project.
- **Deeper:** The novelty is not merely optimization; it is keeping intervention and execution claims attached to inspectable provenance.
- **Evidence to show:** Clinic chain from S0 through source-plan inspection.
- **Honest boundary:** Novelty here is a hackathon product/interaction claim, not a patent or peer-reviewed research claim.

### Why is this not generic project management?

- **Direct:** Generic project management starts after people already know what to do. ASSEMBLE first proves whether the declared community can execute an initiative and derives a Project from that proof.
- **Deeper:** It has no generic CRUD, task board, arbitrary assignment, comments, or collaboration layer.
- **Evidence to show:** Project creation stays absent until a real feasible proof; assignments/readiness are server-derived.
- **Honest boundary:** Persistence, tasks, reassignment, and collaboration are future work, not hidden features.

### What should we notice in the Project?

- **Direct:** READY is derived from a fresh replayed solve, not typed by the browser. The Project carries assignments, actual and matched team facts, venue, schedule, resources, readiness checks, state identities, and source-plan identity.
- **Deeper:** Metadata affects Project identity, while the source-plan identity binds canonical state content and catalyst path.
- **Evidence to show:** Clinic Project detail, dedicated Project Proof, and Inspector focus.
- **Honest boundary:** The returned Project exists only in the current browser/API response; it is not persisted.

## Technical and adversarial questions

### Why CP-SAT?

- **Direct:** The problem is a finite assignment model with hard requirements, capacities, availability, and an objective, which CP-SAT can solve while returning explicit statuses and assignments.
- **Deeper:** The compiler creates decision variables and grouped hard constraints; replay validates a feasible witness rather than trusting status alone.
- **Evidence to show:** compile totals, OPTIMAL result, assignments, trace, solver statistics.
- **Honest boundary:** The present model is deliberately small and bounded; it is not evidence of city-scale performance.

### Why not ChatGPT or an AI wrapper?

- **Direct:** A language model can produce plausible prose without satisfying every constraint. ASSEMBLE's feasibility and intervention results come from deterministic local code and CP-SAT, with no external LLM in the runtime.
- **Deeper:** Explanations are generated from relax-and-resolve evidence and inventory facts, not free-form generation.
- **Evidence to show:** no API key requirement, solver traces, factual blocker structure.
- **Honest boundary:** AI-assisted tools contributed to development; the product's runtime proof chain does not depend on an LLM.

### Are you claiming artificial intelligence?

- **Direct:** We describe the implemented engine precisely as constraint solving and bounded search, not as a general AI assistant.
- **Deeper:** OR-Tools CP-SAT automates combinatorial reasoning; catalogue planning evaluates disclosed successor states.
- **Evidence to show:** architecture and solver statistics.
- **Honest boundary:** It does not discover new facts, converse, predict impact, or generate actions outside the catalogue.

### Is the unlock truly minimum?

- **Direct:** It is minimum cost among sufficient executable ordered paths of one or two distinct actions from the disclosed finite catalogue.
- **Deeper:** With four actions, all 16 unique length-one and length-two orders are considered. Sufficient paths are ranked by total cost, path length, then action IDs, and the planner uses the same executable order with a separate 20-state cap.
- **Evidence to show:** `candidate_paths_evaluated: 16`, cost-2 training, invalid laptop-only action, insufficient single recruit, valid cost-6 dual recruit, and the dependent-order regression.
- **Honest boundary:** It is not a global minimum over unmodelled real-world interventions.

### How do you generate the explanation?

- **Direct:** The engine relaxes bounded requirement groups, resolves, and returns the groups whose relaxation restores feasibility, plus factual inventory evidence.
- **Deeper:** Missing references remain non-relaxable integrity failures; availability evidence includes people, venue, and resources.
- **Evidence to show:** Clinic requirement group, `required 3`, `available 1`, `shortfall 2`, LEO, run count.
- **Honest boundary:** The explanation is only as complete as the encoded requirement groups and fixture facts.

### What if the input data is wrong?

- **Direct:** Solver correctness cannot make incorrect facts true. ASSEMBLE treats the submitted model as declared evidence and makes its provenance visible.
- **Deeper:** Project creation fails closed unless S0 content and lineage exactly match the authoritative fixture; IDs, types, unknown fields, action catalogues, and paths are validated server-side.
- **Evidence to show:** `COMMUNITY_STATE_MISMATCH`, `INVALID_REQUEST`, and catalogue mismatch tests.
- **Honest boundary:** There is no real-world data collection, verification workflow, or inventory editor yet.

### Why make the transition immutable?

- **Direct:** Keeping S0 unchanged makes the intervention's exact effect and lineage auditable.
- **Deeper:** APPLY copies the state, records parent and successor identities, and returns a machine-readable diff; reapplying a no-op is rejected.
- **Evidence to show:** S0-to-successor header, capability diff, transition tests.
- **Honest boundary:** States are response objects, not persisted revisions or a multi-user event log.

### Why verify after applying the action?

- **Direct:** A changed state is not proof. The interface keeps Clinic blocked until the actual successor returns a feasible solver witness.
- **Deeper:** Proof context binds the result to the exact state/path, preventing a successor solve from being relabelled as an S0 proof.
- **Evidence to show:** pause between APPLY and VERIFY; one VERIFY control; form absent before verification.
- **Honest boundary:** Verification proves only the encoded bounded model, not successful real-world delivery.

### Can the client forge a READY Project?

- **Direct:** No. The client submits authoritative S0, an initiative, explicit path, and normalized metadata; the server validates S0, replays the path, solves again, and derives status and execution fields.
- **Deeper:** Canonical content hashes bind the source plan; INFEASIBLE and UNKNOWN emit no Project.
- **Evidence to show:** Project request/response, source-plan ID, forged capability/quantity/availability/lineage rejections.
- **Honest boundary:** This is strong request validation for the local fixture, not a substitute for authentication or production threat controls.

### What happens when resources compete independently?

- **Direct:** Each current initiative is analysed against the submitted state; the build does not jointly schedule multiple initiatives competing for the same resource.
- **Deeper:** Assignments within one initiative respect its encoded capacity and availability constraints.
- **Evidence to show:** single-initiative request/result and requirements scope.
- **Honest boundary:** Cross-initiative portfolio optimization and reservation are not implemented.

### Will it scale?

- **Direct:** The current fixture and searches are intentionally bounded and deterministic; we have local correctness and build evidence, not a scale claim.
- **Deeper:** The solver has an explicit time limit, action search is finite, and planning is capped at depth two and 20 expanded states.
- **Evidence to show:** solver statistics and planner limits.
- **Honest boundary:** There is no load test, concurrency benchmark, large-instance study, or production service-level objective.

### How fast is it?

- **Direct:** The current local journey completes interactively, and controls acknowledge backend work with honest loading states.
- **Deeper:** The documented 100 ms target applies to visible control reaction, not guaranteed solve completion; solver work has an explicit bound.
- **Evidence to show:** loading labels, solver timings/statistics, current test/build evidence.
- **Honest boundary:** No percentile latency or multi-user throughput claim has been measured.

### How do privacy and security work?

- **Direct:** The current build uses fictional fixture data, strict backend models, rejected unknown fields, authoritative catalogue/state validation, stable errors, and no external LLM, analytics export, or cloud service.
- **Deeper:** Project status and readiness are server-derived; forged states, unsafe extra fields, blank normalized metadata, invalid paths, UNKNOWN, and INFEASIBLE fail closed.
- **Evidence to show:** adversarial tests and security reference.
- **Honest boundary:** There is no authentication, RBAC, encrypted persistence, production deployment hardening, or authorization boundary because the app is localhost-only.

### Is accessibility just responsive styling?

- **Direct:** No. The interface includes native controls, keyboard operation, opaque focus, icon-plus-text status, one scoped live region, 44-pixel targets, reduced motion, high contrast, 200% reflow, and graph/list equivalence.
- **Deeper:** Full platform parity requires the same controls, flows, fields, inventory facts, evidence, and Project capabilities at 320 and 1440; only layout or label presentation may change.
- **Evidence to show:** all five destinations, four Community categories, all eight entities, keyboard focus, graph/list detail, live status, Project Proof/Inspector focus, and the same proof/preferences capability at 320 and 1440. Builder desktop and mobile Lighthouse snapshots scored 100 accessibility with 34 passed and zero failed audits.
- **Honest boundary:** These are WCAG-oriented local Builder checks, not independent M6 acceptance or a formal conformance audit with disabled users.

### What is not implemented?

- **Direct:** Authentication, RBAC, persisted Projects, tasks, project membership, reassignment, notifications, external data, deployment, and public operation are absent.
- **Deeper:** Those capabilities were kept out so the solver-to-Project trust chain could be completed and tested first.
- **Evidence to show:** BUILD_STATUS and requirements non-goals.
- **Honest boundary:** Do not describe roadmap items as partially available.

### What comes next?

- **Direct:** First, test the declared-data and explanation workflow with real community stakeholders. Then add provenance-aware inventory capture and persistence before project-level roles, reassignment, tasks, or larger portfolio solving.
- **Deeper:** Each addition should preserve strict validation, source identity, explainability, accessibility/full parity, and cumulative gates.
- **Evidence to show:** current non-goals and traceability process.
- **Honest boundary:** This is a proposed sequence, not committed scope, funding, or delivery timing.

## Fifteen-second answers

- **What is it?** “ASSEMBLE is a localhost civic-capacity planner that uses deterministic constraint solving to prove feasibility, explain a blocker, compare bounded interventions, verify a successor, and derive an inspectable Project.”
- **Why not ChatGPT?** “The core question is whether every hard constraint can be satisfied. CP-SAT returns an explicit status and witness; an LLM is not in the runtime proof chain.”
- **What is the key demo?** “Clinic needs three digital helpers but has one. Training two existing helpers costs two, creates an immutable successor, and only a fresh verification unlocks Project creation.”
- **Can we trust it?** “Within the fixture, important claims are server-derived, content-bound, replayed, and inspectable; forged or non-feasible Project requests fail closed.”
- **Is it production-ready?** “No. It is a bounded fictional hackathon build with local gates; auth, persistence, real-user validation, scale evidence, and deployment are future work.”
- **Is mobile equivalent?** “The requirement is full parity: the same destinations, Community categories and details, proof flow, fields, evidence, preferences, and Project capability at 320 and 1440, with only layout or label presentation changing.”

## Bridge phrases

- “The direct answer is bounded; let me show the evidence we do have.”
- “That is a roadmap question. In the current build, the enforced boundary is…”
- “The solver proves the encoded model, while the interface exposes where those facts came from.”
- “Minimum here has a precise meaning: lowest cost among sufficient disclosed actions.”
- “I do not want to overstate that result; our current evidence is local builder and independent gate evidence, not real-world impact.”
- “The fastest way to verify that claim is this source-proof control.”
