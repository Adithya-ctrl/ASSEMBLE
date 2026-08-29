# Accessibility reference

## Semantics and keyboard

- The interface uses `main`, header, sections, regions, complementary content, headings, lists, forms, labels, details/summary, and native buttons.
- All six solver actions, initiative choices, community blocks, graph/list control, contrast control, reset, inspector, form fields, Project creation, and source-proof control are keyboard accessible.
- Visible interactive targets are at least 44 by 44 CSS pixels.
- Focus uses an opaque cobalt outline in normal and high-contrast modes.

## Status and announcements

Status uses icon plus text; colour is supplementary. Neutral state is used until a requirement is proven. The interface has one dedicated journey announcement for successful compile/analyse, blocker explanation and shortfall, unlock and cost, successor pending proof, successor verification, and Project creation.

The Clinic must not show Project creation or buildable successor status before a real successor verification result.

## Graph and list parity

Graph View and List View are a labelled semantic group. Both expose the same data from the same community object:

- organisation, person, space, and resource IDs;
- capabilities and languages;
- availability slots;
- space capacity and features;
- resource quantity.

SVG connection lines are decorative and hidden from assistive technology. Text remains authoritative.

## Visual resilience

- Normal and high-contrast token modes are available.
- Reduced-motion preference clamps animations and transitions and stops the loading spinner animation without hiding its label.
- Long state, Project, and source-plan IDs wrap.
- Content reflows at 200% zoom without two-dimensional document scrolling.
- Supported widths are 1440, 1280, 768, 390, and 320 CSS pixels without horizontal document overflow.
- Loading forms use disabled inputs and `aria-busy`; late responses cannot populate a changed Project form.

## Full feature parity

At 320 and 1440 CSS pixels, the same controls, flows, editable fields, evidence, and Project capabilities must remain available. Layout and shortened label presentation may change; capability and evidence may not.

Independent browser replay observed the same visible sequence of 23 controls, three editable Project fields, and complete Project-proof rows at both widths, with no horizontal document overflow and no visible interactive target below 44 by 44 CSS pixels. The Builder replay additionally compared 26 evidence items from the completed Project plus seven selected-team facts at each width. These are local implementation checks, not a formal conformance audit or a user-impact claim.

Use [`../how-to/verify-changes.md`](../how-to/verify-changes.md) for the browser acceptance procedure.
