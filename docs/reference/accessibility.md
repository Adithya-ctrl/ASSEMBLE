# Accessibility reference

## Semantics and keyboard

- The interface uses `main`, header, sections, regions, complementary content, headings, lists, forms, labels, details/summary, and native buttons.
- Product navigation, all six solver actions, initiative choices, Community category tabs and entity rows, graph/list control, the three Resilience tasks, appearance choices, contextual reset, Inspector, form fields, Project creation, and source-proof controls are keyboard accessible.
- Visible interactive targets are at least 44 by 44 CSS pixels.
- Focus uses an opaque cobalt outline in normal and high-contrast modes.

## Status and announcements

Status uses icon plus text; colour is supplementary. Neutral state is used until a requirement is proven. Each active shell has one scoped application announcement. The product shell preserves the accepted planning announcements for compile/analyse, blocker and shortfall, unlock and cost, successor pending proof, verification and Project creation, and routes account-menu session changes through that same region. The independent account shell announces identity, Settings and Collaboration actions without mounting a competing product region.

The Clinic must not show Project creation or buildable successor status before a real successor verification result.

## Graph and list parity

Graph View and List View are a labelled semantic group inside the selected Community category. Both derive from the same community object. Human summaries are visible first; a single selected detail surface carries useful full facts, while exact IDs and slots appear only in its Technical details disclosure, Judge Proof Mode, or the Inspector. Across those layers both representations expose the same:

- organisation, person, space, and resource IDs;
- capabilities and languages;
- availability slots;
- space capacity and features;
- resource quantity.

SVG connection lines are decorative and hidden from assistive technology. Text remains authoritative.

Human-facing availability labels are sorted chronologically from a copied array; technical/source order remains unchanged. Product scenes have human alternatives when they add route context and empty alternatives when adjacent copy already communicates the same non-data-bearing visual. Scene motion is not required to understand status, proof, or navigation.

## Visual resilience

- System, light, dark, standard-contrast, and high-contrast token modes are available.
- Only theme, contrast, motion, and preferred inventory view persist in the strict versioned `assemble_ui_preferences` cookie. Judge Proof Mode resets with the browser session and is never stored as account or security data.
- Reduced-motion preference clamps animations and transitions and stops the loading spinner animation without hiding its label.
- Long state, Project, and source-plan IDs wrap.
- Content reflows at 200% zoom without two-dimensional document scrolling.
- Supported widths are 1440, 1280, 768, 390, and 320 CSS pixels without horizontal document overflow.
- Loading forms use disabled inputs and `aria-busy`; late responses cannot populate a changed Project form.

## Full feature parity

At 320 and 1440 CSS pixels, the same controls, flows, editable fields, evidence, Project capabilities, and Resilience tasks must remain available. Layout and shortened label presentation may change; capability and evidence may not.

The accepted cumulative replay traversed every product route at 320, 390 and 1440 and covered the full proof journey, Community parity, Projects, appearance preferences, Judge Proof Mode, guest and authenticated account menus, identity entry, Account/Security/Appearance Settings, Collaboration tasks, Administrator tabs, Viewer read-only access, token focus restoration, Resilience tasks and the shared product live region. It found no document overflow or effective interactive target below 44 by 44 CSS pixels; light, dark, light-high and dark-high surfaces retained strong measured contrast. Earlier desktop/mobile Lighthouse accessibility snapshots scored 100 with 34 passed audits and no failed audits. These are local implementation checks, not formal WCAG conformance, real-user validation, public-deployment evidence or an impact claim.

Use [`../how-to/verify-changes.md`](../how-to/verify-changes.md) for the browser acceptance procedure.
