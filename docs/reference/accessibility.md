# Accessibility reference

## Semantics and keyboard

- The interface uses `main`, header, sections, regions, complementary content, headings, lists, forms, labels, details/summary, and native buttons.
- Product navigation, all six solver actions, initiative choices, Community category tabs and entity rows, graph/list control, appearance choices, reset, Inspector, form fields, Project creation, and source-proof controls are keyboard accessible.
- Visible interactive targets are at least 44 by 44 CSS pixels.
- Focus uses an opaque cobalt outline in normal and high-contrast modes.

## Status and announcements

Status uses icon plus text; colour is supplementary. Neutral state is used until a requirement is proven. The interface has one dedicated journey announcement for successful compile/analyse, blocker explanation and shortfall, unlock and cost, successor pending proof, successor verification, and Project creation.

The Clinic must not show Project creation or buildable successor status before a real successor verification result.

## Graph and list parity

Graph View and List View are a labelled semantic group inside the selected Community category. Both derive from the same community object. Human summaries are visible first; a single selected detail surface carries useful full facts, while exact IDs and slots appear only in its Technical details disclosure, Judge Proof Mode, or the Inspector. Across those layers both representations expose the same:

- organisation, person, space, and resource IDs;
- capabilities and languages;
- availability slots;
- space capacity and features;
- resource quantity.

SVG connection lines are decorative and hidden from assistive technology. Text remains authoritative.

## Visual resilience

- System, light, dark, standard-contrast, and high-contrast token modes are available.
- Only theme, contrast, motion, and preferred inventory view persist in the strict versioned `assemble_ui_preferences` cookie. Judge Proof Mode resets with the browser session and is never stored as account or security data.
- Reduced-motion preference clamps animations and transitions and stops the loading spinner animation without hiding its label.
- Long state, Project, and source-plan IDs wrap.
- Content reflows at 200% zoom without two-dimensional document scrolling.
- Supported widths are 1440, 1280, 768, 390, and 320 CSS pixels without horizontal document overflow.
- Loading forms use disabled inputs and `aria-busy`; late responses cannot populate a changed Project form.

## Full feature parity

At 320 and 1440 CSS pixels, the same controls, flows, editable fields, evidence, and Project capabilities must remain available. Layout and shortened label presentation may change; capability and evidence may not.

The current Builder replay traversed every route at 320 and 1440, reached all five primary navigation destinations, all eight Community entities, the same category/detail and graph/list capabilities, all six proof actions, three editable Project fields, complete Project detail and source proof, Preferences, Judge Proof Mode, and the account-boundary status. It found no document or mobile-navigation overflow and no visible interactive target below 44 by 44 CSS pixels. Desktop and mobile Lighthouse accessibility snapshots scored 100 with 34 passed audits and no failed audits. These are local implementation checks, not formal WCAG conformance, independent M6 acceptance, real-user validation, or an impact claim.

Use [`../how-to/verify-changes.md`](../how-to/verify-changes.md) for the browser acceptance procedure.
