"""Read-only GAUNTLET-ABSOLUTE-01 documentation and coverage audit.

This module deliberately has no product imports and no filesystem writes.  It
is safe to run against a dirty checkout: the audit observes tracked and
untracked source files but only reports findings.  The command-line entry
point emits JSON and returns a non-zero status when a release-relevant finding
is present, so a caller cannot accidentally treat a documentation HOLD as a
pass.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TESTED_QA_SOURCE_HEAD = "a8b9797017668fcc4ae6e9634e2e67d7975ba23d"
TESTED_BROWSER_PRODUCT_HEAD = "453c84fc9c05495b1d21b91f505d8179019f296c"
GAUNTLET_SPEC_SHA256 = "97ab573c7e3b99dcee2f9a0bb9d7e00cb338b0a8714fc81a7604f5ff49b8f1f4"

FR_IDS = [f"FR-{number:03d}" for number in range(1, 24)]
NFR_IDS = [f"NFR-{number:03d}" for number in range(1, 14)]
US_IDS = [f"US-{number:03d}" for number in range(1, 18)]
NUMBERED_REQUIREMENT_IDS = [*FR_IDS, *NFR_IDS]

# Presence is not execution.  These are the independently authored category
# artifacts that the adversarial packet claims to cover; a missing artifact is
# a structural gap even when ordinary product tests remain green.
REQUIRED_TEST_CATEGORIES = {
    "auth-crypto": "backend/tests/adversarial/auth/test_crypto_parser.py",
    "auth-validation": "backend/tests/adversarial/auth/test_validation_boundaries.py",
    "auth-persistence": "backend/tests/adversarial/auth/test_persistence_boundaries.py",
    "auth-lifecycle-rbac": "backend/tests/adversarial/auth/test_lifecycle_rbac.py",
    "http-route-contract": "backend/tests/adversarial/http/test_route_contract_abuse.py",
    "auth-http-route-contract": "backend/tests/adversarial/http/test_auth_route_contract_abuse.py",
    "domain-model-boundaries": "backend/tests/adversarial/models/test_domain_boundaries.py",
    "request-project-boundaries": "backend/tests/adversarial/models/test_request_project_boundaries.py",
    "solver-regression-metamorphic": "backend/tests/adversarial/solver/test_oracle_matrix.py",
    "independent-solver-oracle": "backend/tests/adversarial/independent_solver/test_exhaustive_oracle.py",
    "witness-explain-unlock-oracle": "backend/tests/adversarial/witness_explain_unlock/test_explanation_matrix.py",
    "structural-resilience-oracle": "backend/tests/adversarial/resilience_oracles/test_structural_oracle.py",
    "recompiler-oracle": "backend/tests/adversarial/resilience_oracles/test_recompiler_oracle.py",
    "frontier-oracle": "backend/tests/adversarial/resilience_oracles/test_frontier_oracle.py",
    "browser-artifact": "tests/adversarial/browser-harness/artifact.test.ts",
    "browser-parser": "tests/adversarial/browser-harness/parser-matrix.test.ts",
    "browser-stale-response": "tests/adversarial/browser-harness/stale-response.test.ts",
    "browser-state-machine": "tests/adversarial/browser-harness/state-machines.test.ts",
    "browser-matrix-inventory": "tests/adversarial/browser-harness/BROWSER_MATRIX_PREPARED.md",
    "browser-gap-map": "tests/adversarial/browser-harness/NONVISUAL_GAP_MAP.md",
    "browser-runtime-harness": "tests/adversarial/browser/final_marathon_phase1_29.mjs",
    "browser-evidence-ledger": "tests/adversarial/evidence/browser/final-453c84f/EVIDENCE.md",
}

DOC_ROUTE_RE = re.compile(
    r"^\| (GET|POST|PATCH) \| `(/api/[^`]+)` \| (\d{3}) \|",
    re.MULTILINE,
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def current_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _constant(value: ast.AST | None, default: Any = None) -> Any:
    return value.value if isinstance(value, ast.Constant) else default


def route_decorators() -> list[tuple[str, str, int, str, int]]:
    """Return route decorators without importing FastAPI or application code."""

    routes: list[tuple[str, str, int, str, int]] = []
    for source in sorted((ROOT / "backend" / "app").rglob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in function.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute):
                    continue
                method = decorator.func.attr.lower()
                if method not in {"get", "post", "patch"} or not decorator.args:
                    continue
                path = _constant(decorator.args[0])
                if not isinstance(path, str) or not path.startswith("/api/"):
                    continue
                status = 200
                for keyword in decorator.keywords:
                    if keyword.arg == "status_code":
                        status = _constant(keyword.value, status)
                routes.append(
                    (method.upper(), path, int(status), str(source.relative_to(ROOT)), function.lineno)
                )
    return sorted(routes, key=lambda item: (item[1], item[0]))


def documented_routes() -> list[tuple[str, str, int]]:
    return sorted(
        [(method, path, int(status)) for method, path, status in DOC_ROUTE_RE.findall(_read("docs/reference/api.md"))],
        key=lambda item: (item[1], item[0]),
    )


def markdown_files() -> list[Path]:
    paths = [ROOT / "README.md", ROOT / "BUILD_STATUS.md"]
    paths.extend(sorted((ROOT / "contracts").glob("*.md")))
    paths.extend(sorted((ROOT / "docs").rglob("*.md")))
    paths.extend(sorted((ROOT / "tests" / "adversarial").rglob("*.md")))
    return paths


def broken_local_links() -> list[dict[str, str]]:
    broken: list[dict[str, str]] = []
    for source in markdown_files():
        text = source.read_text(encoding="utf-8")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            relative_target = target.split("#", 1)[0]
            if not relative_target:
                continue
            target_path = (source.parent / relative_target).resolve()
            if not target_path.exists():
                line = text[: text.find(f"]({target})")].count("\n") + 1
                broken.append(
                    {
                        "source": str(source.relative_to(ROOT)),
                        "line": str(line),
                        "target": target,
                    }
                )
    return broken


def requirement_inventory() -> dict[str, Any]:
    requirements = _read("docs/reference/requirements.md")
    traceability = _read("docs/TRACEABILITY.md")
    observed = {
        "FR": re.findall(r"^- \*\*(FR-\d{3})", requirements, re.MULTILINE),
        "NFR": re.findall(r"^- \*\*(NFR-\d{3})", requirements, re.MULTILINE),
        "US": re.findall(r"^### (US-\d{3})", requirements, re.MULTILINE),
    }
    expected = {"FR": FR_IDS, "NFR": NFR_IDS, "US": US_IDS}
    missing_traceability = [
        identifier
        for identifier in (*FR_IDS, *NFR_IDS, *US_IDS)
        if identifier not in traceability
    ]
    return {
        "expected": {key: len(value) for key, value in expected.items()},
        "observed": {key: len(value) for key, value in observed.items()},
        "sequences_match": observed == expected,
        "traceability_missing": missing_traceability,
        "traceability_complete": not missing_traceability,
    }


def traceability_source_gaps() -> list[dict[str, str]]:
    """Check code-formatted traceability paths that are actual local paths."""

    gaps: list[dict[str, str]] = []
    text = _read("docs/TRACEABILITY.md")
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("|") or "`" not in line:
            continue
        for token in re.findall(r"`([^`]+)`", line):
            # Traceability prose occasionally uses a code span for a concept;
            # only path-shaped spans are checked here.
            if "/" not in token or any(char.isspace() for char in token):
                continue
            normalized = token.rstrip("/")
            if "*" in normalized:
                continue
            if not (ROOT / normalized).exists():
                gaps.append({"line": str(line_number), "path": token})
    return gaps


def traceability_requirement_gaps() -> dict[str, Any]:
    """Require every numbered FR/NFR row to name implementation and evidence."""

    text = _read("docs/TRACEABILITY.md")
    rows: dict[str, dict[str, str]] = {}
    in_numbered_table = False
    for line_number, line in enumerate(text.splitlines(), 1):
        if line.startswith("| IDs | Implementation or governing source | Primary evidence |"):
            in_numbered_table = True
            continue
        if not in_numbered_table:
            continue
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or set(cells) == {"---"}:
            continue
        ids = re.findall(r"(?:FR|NFR)-\d{3}", cells[0])
        if not ids:
            continue
        for identifier in ids:
            rows[identifier] = {
                "line": str(line_number),
                "implementation": cells[1],
                "evidence": cells[2],
            }
    missing = [identifier for identifier in NUMBERED_REQUIREMENT_IDS if identifier not in rows]
    empty = [
        {"id": identifier, **rows[identifier]}
        for identifier in NUMBERED_REQUIREMENT_IDS
        if identifier in rows and (not rows[identifier]["implementation"] or not rows[identifier]["evidence"])
    ]
    return {
        "expected_rows": len(NUMBERED_REQUIREMENT_IDS),
        "observed_rows": len(rows),
        "missing": missing,
        "empty": empty,
        "complete": not missing and not empty,
    }


def adversarial_category_inventory() -> dict[str, Any]:
    missing = {
        category: relative
        for category, relative in REQUIRED_TEST_CATEGORIES.items()
        if not (ROOT / relative).exists()
    }
    return {
        "expected": len(REQUIRED_TEST_CATEGORIES),
        "present": len(REQUIRED_TEST_CATEGORIES) - len(missing),
        "missing": missing,
        "complete": not missing,
    }


def stale_current_claims() -> list[dict[str, str]]:
    """Find known superseded claims in current-state sources.

    ADRs are intentionally excluded: the documentation constitution assigns
    historical decisions to ADRs.  Contract pointers are current executable
    sources and therefore are not exempt from drift checks.
    """

    patterns = (
        (
            "contracts/api.md",
            re.compile(r"none of the auth or M7 APIs has a current frontend workflow", re.I),
            "The current API pointer denies frontend auth/M7 workflows, but account and Resilience routes exist.",
        ),
        (
            "contracts/technical-differentiation-api.md",
            re.compile(r"current frontend has no\s*surface for these analyses", re.I),
            "The technical contract denies a frontend Resilience surface, but /resilience is implemented.",
        ),
    )
    findings: list[dict[str, str]] = []
    for relative, pattern, reason in patterns:
        text = _read(relative)
        match = pattern.search(text)
        if not match:
            continue
        findings.append(
            {
                "severity": "HOLD",
                "source": relative,
                "line": str(text[: match.start()].count("\n") + 1),
                "claim": match.group(0),
                "reason": reason,
            }
        )
    return findings


def required_frontend_surfaces() -> dict[str, Any]:
    required = {
        "/": "frontend/app/(product)/page.tsx",
        "/community": "frontend/app/(product)/community/page.tsx",
        "/initiatives": "frontend/app/(product)/initiatives/page.tsx",
        "/initiatives/[initiativeId]/proof": "frontend/app/(product)/initiatives/[initiativeId]/proof/page.tsx",
        "/projects": "frontend/app/(product)/projects/page.tsx",
        "/projects/proof": "frontend/app/(product)/projects/proof/page.tsx",
        "/resilience": "frontend/app/(product)/resilience/page.tsx",
        "/login": "frontend/app/(account)/login/page.tsx",
        "/signup": "frontend/app/(account)/signup/page.tsx",
        "/settings": "frontend/app/(account)/settings/page.tsx",
        "/preferences (redirect)": "frontend/app/(account)/preferences/page.tsx",
        "/communities": "frontend/app/(account)/communities/page.tsx",
        "/communities/[communityId]": "frontend/app/(account)/communities/[communityId]/page.tsx",
    }
    missing = [path for path, relative in required.items() if not (ROOT / relative).exists()]
    return {
        "expected_page_files": len(required),
        "actual_page_files": len(list((ROOT / "frontend" / "app").rglob("page.tsx"))),
        "missing": missing,
        "complete": not missing,
    }


def audit() -> dict[str, Any]:
    head = current_head()
    decorators = route_decorators()
    documented = documented_routes()
    route_mismatch = {
        "documented_not_implemented": [item for item in documented if item not in {route[:3] for route in decorators}],
        "implemented_not_documented": [route[:3] for route in decorators if route[:3] not in set(documented)],
    }
    requirements = requirement_inventory()
    requirement_rows = traceability_requirement_gaps()
    links = broken_local_links()
    traceability_gaps = traceability_source_gaps()
    test_categories = adversarial_category_inventory()
    stale_claims = stale_current_claims()
    frontend = required_frontend_surfaces()
    structural_failures = []
    if route_mismatch["documented_not_implemented"] or route_mismatch["implemented_not_documented"]:
        structural_failures.append("documented API route table differs from Python route decorators")
    if not requirements["sequences_match"] or not requirements["traceability_complete"]:
        structural_failures.append("numbered requirements are incomplete or not traceable")
    if not requirement_rows["complete"]:
        structural_failures.append("one or more numbered traceability rows lack implementation or evidence")
    if links:
        structural_failures.append("one or more local documentation links are broken")
    if traceability_gaps:
        structural_failures.append("one or more traceability source paths are missing")
    if not frontend["complete"]:
        structural_failures.append("required frontend route surface is incomplete")
    if not test_categories["complete"]:
        structural_failures.append("one or more adversarial test categories are missing")
    findings = [*stale_claims]
    status = "HOLD" if structural_failures or findings else "PASS"
    return {
        "audit": "B2-G6",
        "status": status,
        "authority": {
            "checkout": str(ROOT),
            "artifact_context_head": head,
            "tested_qa_source_head": TESTED_QA_SOURCE_HEAD,
            "tested_browser_product_head": TESTED_BROWSER_PRODUCT_HEAD,
            "gauntlet_spec_sha256": GAUNTLET_SPEC_SHA256,
            "browser_execution": "EXECUTED_ON_SEPARATELY_PINNED_PRODUCT_SOURCE",
        },
        "structural": {
            "route_decorators": len(decorators),
            "documented_route_rows": len(documented),
            "route_mismatch": route_mismatch,
            "requirements": requirements,
            "traceability_requirement_rows": requirement_rows,
            "broken_local_links": links,
            "traceability_source_gaps": traceability_gaps,
            "test_categories": test_categories,
            "frontend_surfaces": frontend,
            "failures": structural_failures,
        },
        "findings": findings,
        "known_environment_gaps": [
            "Firefox and WebKit/Safari were not verified.",
            "Requested 400% browser zoom was capped at measured 300% by Chrome 151 headless/CDP.",
            "The complete visual Cartesian matrix and every mounted async/parser/RBAC race permutation were not executed.",
        ],
    }


def main() -> int:
    result = audit()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
