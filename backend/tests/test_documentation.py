from __future__ import annotations

from pathlib import Path
import re

from app.main import app


ROOT = Path(__file__).parents[2]
DOCS = ROOT / "docs"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _current_markdown_files() -> list[Path]:
    return [
        ROOT / "README.md",
        ROOT / "BUILD_STATUS.md",
        *sorted((ROOT / "contracts").glob("*.md")),
        *sorted(path for path in DOCS.rglob("*.md") if "adr" not in path.parts),
    ]


def test_current_documentation_has_no_broken_local_links() -> None:
    broken: list[str] = []
    sources = [
        ROOT / "README.md",
        ROOT / "BUILD_STATUS.md",
        *sorted((ROOT / "contracts").glob("*.md")),
        *sorted(DOCS.rglob("*.md")),
    ]
    for source in sources:
        for target in MARKDOWN_LINK.findall(source.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = target.split("#", 1)[0]
            if path_text and not (source.parent / path_text).resolve().exists():
                broken.append(f"{source.relative_to(ROOT)} -> {target}")
    assert broken == []


def test_docs_index_exposes_diat_axis_and_governance_roles() -> None:
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    for section in ("tutorials/", "how-to/", "reference/", "explanation/", "adr/"):
        assert section in index
    for role in ("Constitution", "Map", "Status", "History"):
        assert role in index
    assert "UI_DIRECTION.md" in index
    assert "identity-community-invitations.md" in index
    assert "technical-differentiation.md" in index


def test_api_reference_matches_current_openapi_routes() -> None:
    reference = (DOCS / "reference" / "api.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`(/api/[^`]+)`", reference))
    openapi = app.openapi()
    assert documented == set(openapi["paths"])

    documented_operations = {
        (method, route, success)
        for method, route, success in re.findall(
            r"^\| (GET|POST|PATCH) \| `(/api/[^`]+)` \| (\d{3}) \|",
            reference,
            flags=re.MULTILINE,
        )
    }
    openapi_operations = {
        (
            method.upper(),
            route,
            sorted(code for code in operation["responses"] if code.startswith("2"))[0],
        )
        for route, operations in openapi["paths"].items()
        for method, operation in operations.items()
    }
    assert documented_operations == openapi_operations

    stable_codes = {
        "INVALID_REQUEST",
        "INVALID_REFERENCE",
        "INVALID_ACTION_CATALOGUE",
        "ACTION_CATALOGUE_MISMATCH",
        "ACTION_ALREADY_APPLIED",
        "ALREADY_FEASIBLE",
        "TRANSITION_NOT_ALLOWED",
        "NO_UNLOCK_PATH",
        "NO_PLAN_FOUND",
        "COMMUNITY_STATE_MISMATCH",
        "PROJECT_PLAN_NOT_FEASIBLE",
        "ROUTE_NOT_FOUND",
        "METHOD_NOT_ALLOWED",
        "ANALYSER_CONTRACT_ERROR",
        "HTTP_ERROR",
        "ACCOUNT_UNAVAILABLE",
        "AUTHENTICATION_FAILED",
        "AUTHENTICATION_REQUIRED",
        "PERMISSION_DENIED",
        "COMMUNITY_UNAVAILABLE",
        "COMMUNITY_NOT_FOUND",
        "MEMBERSHIP_NOT_FOUND",
        "MEMBERSHIP_EXISTS",
        "PENDING_INVITATION_EXISTS",
        "INVITATION_NOT_AVAILABLE",
        "INVITATION_NOT_PENDING",
        "LAST_ADMINISTRATOR_REQUIRED",
        "RATE_LIMITED",
        "SERVICE_BUSY",
        "UNSUPPORTED_MEDIA_TYPE",
        "BROWSER_ORIGIN_REJECTED",
    }
    assert stable_codes <= set(re.findall(r"^\| `([A-Z_]+)` \|", reference, flags=re.MULTILINE))


def test_project_security_contract_and_current_status_are_documented() -> None:
    project = (DOCS / "reference" / "project-contract.md").read_text(encoding="utf-8")
    security = (DOCS / "reference" / "security-validation.md").read_text(encoding="utf-8")
    status = (ROOT / "BUILD_STATUS.md").read_text(encoding="utf-8")
    for code in ("COMMUNITY_STATE_MISMATCH", "PROJECT_PLAN_NOT_FEASIBLE"):
        assert code in project
        assert code in security
    assert "P0-A Project and integrity hardening is independently accepted" in status
    assert "279 passed" in status

    for ceiling in (
        "Organisations in a community | 32",
        "People in a community | 128",
        "Spaces in a community | 32",
        "Resources in a community | 64",
        "Catalyst actions in a submitted catalogue | 32",
        "Languages per person or role | 16",
    ):
        assert ceiling in security
    assert "candidate_paths_evaluated" in (DOCS / "reference" / "requirements.md").read_text(encoding="utf-8")


def test_conventional_commit_and_same_change_docs_policy_are_documented() -> None:
    contributing = (DOCS / "how-to" / "contributing.md").read_text(encoding="utf-8")
    assert "<type>(<scope>): <imperative summary>" in contributing
    assert "documentation" in contributing.lower()
    assert "traceability" in contributing.lower()
    assert "same change" in contributing.lower()
    assert "accepted milestone" in contributing
    assert "do not push another commit" in contributing.lower()
    assert "BUILD_STATUS.md" in contributing


def test_current_docs_do_not_preserve_known_superseded_contract_history() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _current_markdown_files())
    for stale_marker in (
        "Frozen API contract — M0",
        "/api/reassemble",
        "## 3. Explored directions",
        "candidate_subsets_evaluated",
        "Authentication and role-based access control are not current capabilities",
        "It is executable only after the control centre registers the router",
        "After reviewing and accepting the isolated slice",
    ):
        assert stale_marker not in combined


def test_numbered_requirements_are_consecutive_mapped_and_traceable() -> None:
    requirements = (DOCS / "reference" / "requirements.md").read_text(encoding="utf-8")
    traceability = (DOCS / "TRACEABILITY.md").read_text(encoding="utf-8")

    expected_fr = [f"FR-{number:03d}" for number in range(1, 24)]
    expected_nfr = [f"NFR-{number:03d}" for number in range(1, 14)]
    expected_us = [f"US-{number:03d}" for number in range(1, 18)]
    assert re.findall(r"^- \*\*(FR-\d{3})", requirements, flags=re.MULTILINE) == expected_fr
    assert re.findall(r"^- \*\*(NFR-\d{3})", requirements, flags=re.MULTILINE) == expected_nfr
    assert re.findall(r"^### (US-\d{3})", requirements, flags=re.MULTILINE) == expected_us

    known_requirements = set(expected_fr + expected_nfr)
    story_blocks = re.split(r"(?=^### US-\d{3})", requirements, flags=re.MULTILINE)[1:]
    assert len(story_blocks) == len(expected_us)
    for story in story_blocks:
        assert "Maps to " in story
        assert all(token in story for token in ("**Given**", "**when**", "**then**"))
        mapping_line = next(line for line in story.splitlines() if "Maps to " in line)
        mapped_ids = set(re.findall(r"(?:FR|NFR)-\d{3}", mapping_line))
        assert mapped_ids
        assert mapped_ids <= known_requirements

    for requirement_id in (*expected_fr, *expected_nfr, *expected_us):
        assert requirement_id in traceability


def test_presentation_package_is_linked_timed_and_bounded() -> None:
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    overview = (DOCS / "presentation" / "project-overview.md").read_text(encoding="utf-8")
    video = (DOCS / "presentation" / "three-minute-video.md").read_text(encoding="utf-8")
    live_demo = (DOCS / "presentation" / "four-minute-live-demo.md").read_text(encoding="utf-8")
    questions = (DOCS / "presentation" / "judge-questions.md").read_text(encoding="utf-8")

    for name in ("project-overview.md", "three-minute-video.md", "four-minute-live-demo.md", "judge-questions.md"):
        assert f"presentation/{name}" in index
    assert not (DOCS / "tutorials" / "video-demo-script.md").exists()

    def seconds(timestamp: str) -> int:
        minutes, remainder = timestamp.split(":")
        return int(minutes) * 60 + int(remainder)

    def timeline(document: str) -> list[tuple[int, int]]:
        return [
            (seconds(start), seconds(end))
            for start, end in re.findall(r"^\| (\d:\d{2})–(\d:\d{2}) \|", document, flags=re.MULTILINE)
        ]

    assert timeline(video) == [
        (0, 18), (18, 35), (35, 55), (55, 78), (78, 102),
        (102, 124), (124, 145), (145, 168), (168, 180),
    ]
    assert timeline(live_demo) == [
        (0, 20), (20, 42), (42, 64), (64, 90), (90, 118),
        (118, 144), (144, 165), (165, 200), (200, 222), (222, 240),
    ]
    for heading in ("## Problem", "## Audience", "## Purpose", "## Current scope and limits"):
        assert heading in overview
    for heading in ("## Recording checklist", "## No-overclaim guardrails"):
        assert heading in video
    for heading in ("## Reset-based recovery", "## Shortened fallback for a stalled action"):
        assert heading in live_demo
    for heading in ("## Friendly questions", "## Technical and adversarial questions", "## Fifteen-second answers", "## Bridge phrases"):
        assert heading in questions

    combined = "\n".join((overview, video, live_demo, questions)).lower()
    for boundary in (
        "fictional",
        "bounded",
        "frontend has no identity or m7 workflow",
        "not role-gated",
        "projects and proof state remain in memory",
        "production deployment",
    ):
        assert boundary in combined
    for overclaim in ("assemble is production-ready", "assemble is deployed", "guaranteed real-world impact"):
        assert overclaim not in combined


def test_documentation_audit_and_full_parity_are_wired() -> None:
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    audit = (DOCS / "how-to" / "audit-documentation.md").read_text(encoding="utf-8")
    contributing = (DOCS / "how-to" / "contributing.md").read_text(encoding="utf-8")
    verify = (DOCS / "how-to" / "verify-changes.md").read_text(encoding="utf-8")
    requirements = (DOCS / "reference" / "requirements.md").read_text(encoding="utf-8")
    accessibility = (DOCS / "reference" / "accessibility.md").read_text(encoding="utf-8")

    assert "how-to/audit-documentation.md" in index
    assert "Layer A" in audit and "Layer B" in audit
    assert "tutorials/video-demo-script.md" not in audit
    assert "presentation/project-overview.md" in audit
    for source in ("README.md", "requirements.md", "api.md", "security-validation.md", "accessibility.md", "BUILD_STATUS.md"):
        assert source in audit
    assert "audit-documentation.md" in contributing
    assert "audit-documentation.md" in verify
    assert "must not be accepted, committed, or pushed" in contributing

    parity_sources = "\n".join((requirements, accessibility, audit))
    for evidence in (
        "320",
        "1440",
        "three editable",
        "all eight",
        "Community categories",
        "Project capabilities",
        "navigation",
    ):
        assert evidence in parity_sources


def test_modular_interface_contract_is_current_and_traceable() -> None:
    requirements = (DOCS / "reference" / "requirements.md").read_text(encoding="utf-8")
    architecture = (DOCS / "explanation" / "architecture.md").read_text(encoding="utf-8")
    accessibility = (DOCS / "reference" / "accessibility.md").read_text(encoding="utf-8")
    traceability = (DOCS / "TRACEABILITY.md").read_text(encoding="utf-8")
    status = (ROOT / "BUILD_STATUS.md").read_text(encoding="utf-8")
    combined = "\n".join((requirements, architecture, accessibility, traceability, status))

    for route in (
        "Overview",
        "Community",
        "Initiatives",
        "Initiative Proof",
        "Projects",
        "Project Proof",
        "Preferences",
    ):
        assert route in combined
    for contract in (
        "assemble_ui_preferences",
        "Judge Proof Mode",
        "session-only",
        "invalid, oversized, or stale-version",
        "all eight",
        "independently accepted",
    ):
        assert contract in combined

    for stale_claim in (
        "app/page.tsx",
        "None of these future roles, navigation changes",
        "multi-page product experience are the next",
    ):
        assert stale_claim not in combined


def test_integrated_auth_and_m7_boundaries_are_current_and_traceable() -> None:
    requirements = (DOCS / "reference" / "requirements.md").read_text(encoding="utf-8")
    traceability = (DOCS / "TRACEABILITY.md").read_text(encoding="utf-8")
    architecture = (DOCS / "explanation" / "architecture.md").read_text(encoding="utf-8")
    security = (DOCS / "reference" / "security-validation.md").read_text(encoding="utf-8")
    auth = (DOCS / "reference" / "identity-community-invitations.md").read_text(encoding="utf-8")
    m7 = (DOCS / "reference" / "technical-differentiation.md").read_text(encoding="utf-8")
    guide = (DOCS / "how-to" / "integrate-auth-backend.md").read_text(encoding="utf-8")
    status = (ROOT / "BUILD_STATUS.md").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    combined = "\n".join((requirements, traceability, architecture, security, auth, m7, guide, status))

    for contract in (
        "backend/.data/auth.sqlite3",
        "ASSEMBLE_AUTH_ALLOWED_BROWSER_ORIGINS",
        "0700",
        "0600",
        "not linked to the solver",
        "not role-gated",
        "no current frontend",
        "remain in memory",
        "counterfactual",
    ):
        assert contract in combined
    assert "backend/.data/" in gitignore
    for route in ("/api/auth/signup", "/api/stress-test", "/api/recompile", "/api/frontier"):
        assert route in app.openapi()["paths"]

    assert "Do not apply it again" in guide
    assert "at most 32 unique entries and 4096 UTF-8 bytes" in guide
    assert "/api/authentic" in guide and "ordinary application 404" in guide
