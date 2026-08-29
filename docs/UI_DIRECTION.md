# ASSEMBLE UI Direction and Acceptance Contract

Status: frozen direction for the event-day redesign. This document adapts premium commercial-design methods to a civic planning application. It is not a landing-page brief.

## 1. Product truth

ASSEMBLE helps a community answer three concrete questions:

1. What people, capabilities, spaces, equipment, time, and organisational relationships do we have?
2. Which community initiatives are feasible with those blocks now, and what exact evidence supports that result?
3. When an initiative is blocked, what is the smallest valid intervention that makes it feasible, and does the changed successor state prove it?

The primary user is a community coordinator. The primary event-day observer is a judge. The decisive action is not a commercial conversion: it is completing the evidence-backed journey from community state `S0`, through a proven blocker and a valid catalyst, to verified state `S1`.

## 2. Current direction

### Assembly Table with Blueprint Evidence

The interface should feel like a warm community planning table becoming active. People and resources are visually primary. Blueprint-like sockets, seams, and evidence rows expose how requirements connect to capacity. The visual metaphor must remain truthful: a seam or socket represents a real relationship in the backend model, never decoration.

Desired emotional sequence:

- arrival: calm, human, and immediately understandable;
- compile: the community's latent structure becomes visible;
- feasible initiative: confidence grounded in an explicit assignment;
- blocked initiative: concern without alarmism, attached to a factual shortfall;
- unlock: agency through a smallest valid intervention;
- successor state: earned optimism because `S1` is independently solved.

## 3. Reference-role map

References are used for principles and interaction mechanisms only. Do not reproduce their branding, assets, copy, or distinctive compositions.

| Role | Reference | Principle to borrow | Do not borrow |
| --- | --- | --- | --- |
| Identity | [Decidim](https://decidim.org/) | Civic directness, transparent participation, assertive graphic structure | Its palette, branding, or campaign composition |
| Hero / opening state | [Felt UI upgrades](https://felt.com/blog/ui-upgrades) | A map-like workspace begins immediately; restrained controls frame the surface | Geographic map conventions irrelevant to ASSEMBLE |
| Primary canvas | [Kumu system mapping](https://www.kumu.io/markets/system-mapping) | Relationships and focused reveal make a system legible | Infinite graph complexity or force-layout movement |
| Navigation / component behaviour | [Radix Themes](https://www.radix-ui.com/themes/docs/components) | Accessible controls, disclosures, tabs, and state feedback | Default-theme appearance left uncustomised |
| Collaborative structure | [Miro canvas templates](https://miro.com/templates/canvas/) | Bounded workshop zones and shared-planning clarity | Infinite whiteboard, drag-and-drop, sticky-note clutter |
| Technical proof | [Observable Plot](https://observablehq.com/plot/) | Precise marks and restrained technical graphics | Charting where simple facts communicate better |
| Evidence rhythm | [Our World in Data](https://ourworldindata.org/) | Claims remain adjacent to explanation and source context | Editorial page structure or chart catalogue |
| Progressive explanation | [The Pudding](https://pudding.cool/2022/12/emotion-wheel/) | Focus, filtering, pause/reduced-motion, and text alternatives | Scroll hijacking or long-form storytelling |
| Workflow rhythm | [Are.na](https://www.are.na/) | A visible sequence from capture to arrangement to connection makes collective assembly legible | Its black shell, asterisk identity, or channel interface |
| Bounded civic decision | [Pol.is](https://pol.is/home2) | One decision at a time, visible progress, and method output that can be inspected | Its voting treatment, point-cloud palette, or brand typography |
| Civic spatial controls | [Civio Map Builder](https://civ.io/engage/features/spatial-engagement/map-builder/) | Separate place context, layers, parameters, and lifecycle actions cleanly | Its mint palette, rounded media treatment, or publishing workflow |
| Spatial inspiration | [Awwwards Tavalo map](https://www.awwwards.com/inspiration/interactive-map-tavalo) | Spatial focus can guide attention through a neighbourhood system | Decorative WebGL, cinematic transitions, or map branding |
| Curated interaction scan | [Godly](https://godly.website/) | Stable taxonomy and contextual side information reduce navigation cost | Its creator-feed shell, masonry showcase, or trend aesthetics |
| Community composition scan | [SiteInspire community gallery](https://www.siteinspire.com/websites/category/community) | Public-interest warmth and varied body rhythm | Marketing-page architecture |
| Pattern rejection scan | [Dribbble community dashboard search](https://dribbble.com/search/community%20dashboard) | Useful as a catalogue of common dashboard patterns to avoid | Gradient blobs, avatar walls, equal-card grids, vanity metrics |
| Diagram scan | [Pinterest systems-map board](https://ca.pinterest.com/andreafacenda/systems-map/) | Shape and relationship references | Unverified interaction, accessibility, or implementation patterns |

Explicit negative reference: generic gradient SaaS dashboards with soft identical cards. They make the current system look like an AI wrapper and hide its strongest asset: a deterministic, inspectable solver journey.

## 4. Application architecture

The core is a single judge-ready planning workspace followed by a proof-derived Project surface, not a sales homepage or disconnected project-management product.

### Persistent shell

- compact top bar: ASSEMBLE identity, state indicator (`S0` or `S1`), reset control, and inspector disclosure;
- community canvas: organisations, people, capabilities, resources, spaces, and real relationship seams;
- initiative rail: Basic Workshop, Multilingual Clinic, and Repair Skill-Share with status and requirement sockets;
- decision workspace: assignment, blocker evidence, candidate interventions, applied catalyst, and successor proof;
- technical inspector: collapsed by default, containing variable/constraint counts, solve status, objective, trace, state identifier, and exact state diff.
- executable Project: appears only after a real feasible base proof or verified successor proof; contains editable metadata and server-derived operational detail.

### Judge journey

1. `COMPILE COMMUNITY` validates the input model and activates only proven relationships.
2. `ASSEMBLE NOW` solves Basic Workshop and reveals the selected blocks plus assignment trace.
3. `WHY BLOCKED?` focuses Multilingual Clinic and shows the minimum blocking fact set.
4. `FIND MINIMUM UNLOCK` compares the action catalogue and identifies the cheapest valid intervention, not merely the cheapest action.
5. `APPLY CATALYST` creates a new immutable successor state and exposes its diff.
6. `VERIFY NEW STATE` independently solves the clinic in `S1` and closes its requirement sockets only after a successful response.

These labels and this order are frozen for the demo. Controls must never imply success before the backend response.

After the six-action journey, `CREATE PROJECT` is a separate labelled form action. Basic Workshop may create from its feasible S0 proof with explicit path `[]`. Multilingual Clinic must not expose the form until successor verification; it creates from the authoritative `TRAIN_DIGITAL_HELPERS` path. The Project detail shows returned status, operational team, complete selected-person facts, readiness evidence, venue, time, resources, accessibility, languages, source-plan ID, and a control that opens and focuses the Technical Inspector.

## 5. Layout system

### Desktop, 1280px and above

- 12-column grid with restrained 20-24px outer gutters;
- community canvas spans seven columns;
- initiative rail and decision workspace span five columns;
- inspector spans the full content width below or opens as a full-width drawer;
- avoid a dashboard of equally elevated containers: only the selected decision surface receives meaningful elevation;
- use grouping, alignment, hairlines, and whitespace before introducing another box.

### Tablet, 768-1023px

- community canvas first, initiative selector second, decision workspace third;
- preserve a compact two-column arrangement inside organisation zones where readable;
- inspector becomes an accordion;
- no horizontal scrolling.

### Mobile, 320-767px

- one semantic column in task order;
- initiative choices become full-width rows or a labelled segmented control when all labels remain readable;
- SVG seams may disappear, but every relationship must remain available as text rows;
- sticky action area is allowed only when it does not cover content or browser controls;
- tap targets are at least 44 by 44 CSS pixels;
- no hover-only meaning.

## 6. Typography

- Geist: product identity, headings, labels, narrative, controls;
- Geist Mono: state IDs, solver status, counts, costs, constraints, and trace values;
- product title: 26px desktop, 22px mobile, semibold, approximately `-0.015em` tracking;
- primary section title: 17-19px, semibold;
- block name: 14-15px, semibold;
- body and explanation: 14-16px, 1.45-1.55 line height, maximum 58-65 characters per line;
- technical row: 12-13px mono with aggressive wrapping for long identifiers;
- use sentence case. Reserve uppercase for the six explicit action buttons and tiny machine statuses where it aids scanning;
- do not use a giant multi-line headline, repeated eyebrow labels, or monotonous heading scales.

## 7. Colour, material, and graphic grammar

Authoritative palette:

- canvas: `#F6F7F3`;
- surface: `#FFFFFF`;
- graphite text: `#17212B`;
- cobalt action/selection: `#3457D5`;
- semantic green: verified feasible only;
- semantic red: proven blocker/error only;
- semantic amber: warning or non-solving candidate only.

Material rules:

- 12px corners on blocks and panels, 10px on controls, full pills only for compact status tags;
- 1px quiet borders and a single restrained shadow on the active decision surface;
- no gradients, glass, glow, neon, decorative grain, dark cyber styling, or fake paper/wood texture;
- icon plus label plus colour for states; colour alone is never authoritative.

### Block grammar

- person: circular shape cue plus person icon, name, capability line, organisation, and availability;
- capability: certificate/spark shape cue plus explicit capability text;
- resource: equipment shape cue plus quantity and available quantity;
- space: building shape cue plus capacity and accessibility/availability;
- organisation: bounded zone or tray, not another repeated card.

### Connection and requirement grammar

- neutral stitched seam: known relationship not yet solver-validated;
- cobalt seam: relationship used or validated in the current result;
- open socket: missing requirement, always labelled;
- closed socket: satisfied requirement after a verified result;
- blocker proof row: `required`, `available`, `shortfall`, source constraint, and solver-run count when applicable;
- unrelated routes reduce contrast during explanation but remain discoverable.

## 8. Motion grammar

Motion communicates state, causality, or navigation only.

- ordinary state changes: 180-320ms;
- catalyst and `S0 -> S1`: up to 700ms, response-gated;
- compile: neutral seams become cobalt after a successful response;
- assignment: selected blocks receive a restrained outline and the trace enters in reading order;
- explanation: affected requirement and supporting facts focus together;
- catalyst: Priya and Sam gain capability blocks after the transition response; the clinic does not become feasible until verification;
- loading: use labelled progress or skeletons; never fake solver progress percentages;
- reduced motion: all information appears immediately, without geometry animation, parallax, or animated scrolling.

No WebGL or true 3D is required. Shallow depth may distinguish the active decision surface from the quiet canvas. That is the only spatial signature in the core.

## 9. Accessibility and resilience

- semantic landmarks and heading order;
- keyboard access to every action, initiative, inspector control, and reset;
- visible `:focus-visible` states with sufficient contrast;
- status updates announced through an appropriately scoped live region;
- errors persist beside the relevant action and remain readable after focus moves;
- every icon has a text label or is hidden from assistive technology;
- SVG connections are `aria-hidden`; a textual relationship/evidence representation is authoritative;
- minimum WCAG AA contrast for all essential text and controls;
- loading controls use `aria-busy`/disabled semantics without losing labels;
- long IDs and constraint names wrap using `overflow-wrap: anywhere` and never expand the page width;
- the workflow remains usable if animation is disabled or the connection layer fails.

## 10. Performance budget

- use existing React/Next.js, native CSS layout, DOM blocks, and one restrained SVG layer;
- no D3, force-layout, React Flow, WebGL, 3D, physics, video, or large image dependency;
- no new visual dependency without a measured functional need;
- connection geometry is measured after layout and recomputed only on relevant resize/state changes;
- preserve a responsive interaction target: controls visibly react within 100ms, with honest loading feedback during backend work;
- test the production build, not only development mode.

## 11. Always / never guardrails

Always:

- lead with people, capabilities, resources, and the initiative they enable;
- keep backend evidence adjacent to every feasibility or blocker claim;
- visibly distinguish `S0`, the catalyst, the state diff, and verified `S1`;
- distinguish a cheap candidate from a valid minimum unlock;
- make the entire six-action journey possible by keyboard and touch;
- retain honest UNKNOWN, validation, and network-error states.

Never:

- turn the application into a sales landing page, pricing page, or testimonial showcase;
- use repetitive metric cards, decorative charts, avatar walls, or vanity numbers;
- imply an LLM is the source of deterministic solver facts;
- use laptop borrowing as a visual answer to a skills shortage;
- animate before a response or hide a failure behind optimistic UI;
- expose meaning only through hover, colour, connector lines, or motion;
- allow long hashes, traces, or error strings to create horizontal overflow;
- add gamification, confetti, achievement badges, or playful bounce.

## 12. Continuous browser acceptance protocol

Every UI sprint ends with a real-browser replay. A green build alone is insufficient.

### Preconditions

- start the real FastAPI backend and production-like Next.js frontend;
- reset to pristine `S0`;
- clear stale console/network evidence or use a clean page instance;
- record the exact viewport and build identity.

### Functional replay

At minimum, exercise these as a user:

1. load and refresh the application;
2. open and close the technical inspector;
3. `COMPILE COMMUNITY`;
4. select Basic Workshop and `ASSEMBLE NOW`;
5. select Multilingual Clinic and `WHY BLOCKED?`;
6. `FIND MINIMUM UNLOCK`;
7. inspect each candidate and verify invalid/irrelevant options are visibly distinguished;
8. `APPLY CATALYST` once, then verify a second application is rejected honestly;
9. `VERIFY NEW STATE` and confirm the clinic is feasible only in `S1`;
10. confirm Project creation is now available, create the Clinic Project, and open its source proof;
11. separately create Basic Workshop from explicit `[]` after its real S0 proof;
12. compare Graph View and List View for equivalent community facts;
13. reset to `S0` and verify the initial state is restored;
14. test invalid action/state handling where the UI exposes it;
15. navigate every control with keyboard, including Project fields, contrast, view choice, source proof, and focus return from the inspector.

### Viewport replay

- desktop: 1440x900 and 1280x720;
- tablet: 768x1024;
- mobile: 390x844 and a narrow 320px check;
- assert document width does not exceed viewport width at any step;
- visually inspect hierarchy, clipped text, sticky regions, control labels, and inspector wrapping.

### State replay

- pristine and compiled;
- optimal assignment;
- infeasible with blocker facts;
- minimum unlock found;
- transition applied;
- successor verified;
- loading;
- stable API/domain error;
- unavailable backend/network failure;
- reduced motion.

### Evidence to capture

- screenshots at the decisive desktop and mobile states;
- browser console warnings/errors;
- failed network requests and response bodies;
- keyboard focus path and focus visibility;
- overflow measurement;
- exact failing action, expected result, actual result, and state ID.

### Failure handling

Any unexpected browser result places the UI sprint on HOLD. Create a narrowly scoped recovery lane with ownership of the exact defect, preserve the failing evidence, apply the smallest repair, then replay the failed path and the complete cumulative judge journey. A later successful step does not erase an earlier failure.

## 13. Definition of visually accepted

The redesign is accepted only when:

- the product reads as a civic capacity-and-intervention planner within five seconds;
- the community blocks remain visually primary;
- the deterministic proof is visible without opening developer tools;
- all six actions complete the real backend journey;
- desktop and mobile retain the same hierarchy and character;
- keyboard, reduced-motion, error, and long-identifier paths work;
- Basic empty-path and Clinic successor-path Project creation are truthful and complete;
- graph and list views expose equivalent identity and capacity facts;
- production build, typecheck, lint, browser console, network, and overflow gates are green;
- screenshots show a coherent finished system across the opening, blocker, intervention, and verified-success states.
