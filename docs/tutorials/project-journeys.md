# Create an executable Project

This tutorial uses the deterministic fictional demo fixture.

## Basic Workshop: no catalyst required

1. Open ASSEMBLE and choose **Basic Digital Workshop**.
2. Select **COMPILE COMMUNITY**. The backend analyses the authoritative S0 fixture.
3. Confirm the initiative is **Buildable** and the Project form says **Base state / explicit [] path**.
4. Review or edit the generated title, short description, and objective.
5. Select **CREATE PROJECT**.
6. Confirm the returned Project is **READY**, the proof is `S0 -> S0`, and the operational team, venue, time, resource allocation, accessibility, readiness checks, and source plan are visible.

The empty path is explicit. Omitting `catalyst_path` is a validation error.

## Multilingual Clinic: verify the successor first

1. Reset and choose **Multilingual Digital Help Clinic**.
2. Select **COMPILE COMMUNITY**, then **ASSEMBLE NOW**.
3. The S0 result is blocked: one digital helper is available and three are required, a shortfall of two.
4. Select **WHY BLOCKED?** to inspect the solver-confirmed requirement facts.
5. Select **FIND MINIMUM UNLOCK**. The disclosed valid minimum is **Train two digital helpers**, cost 2.
6. Select **APPLY CATALYST**. A new immutable successor state appears, but the Clinic remains blocked pending proof.
7. Confirm **CREATE PROJECT** is not available yet.
8. Select the single **VERIFY NEW STATE** control.
9. After the successor returns `OPTIMAL`, review the Project form. Its path is `TRAIN_DIGITAL_HELPERS`.
10. Select **CREATE PROJECT** and confirm the Project is `READY`.

The operational facts show English for Priya, Leo, and Sam, and Arabic plus English for Amira. Requirement matches remain separately visible from each selected person’s complete capability and language facts.

## Inspect the proof

Select **View source proof** in the Project footer. ASSEMBLE opens and focuses the Technical Inspector, where the current compile, solver, transition, and state evidence can be reviewed.
