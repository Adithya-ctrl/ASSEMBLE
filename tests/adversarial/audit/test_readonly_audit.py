"""Pytest wrapper for the B2-G6 read-only audit.

The wrapper asserts structural invariants and requires the reconciled current
contracts to have no drift. It records immutable tested-source identities
without requiring an artifact commit to contain its own future hash. It does
not turn a known finding into a pass: ``run_readonly_audit.py`` reports
``status: HOLD`` whenever current contract pointers drift and ``PASS`` after
the reconciled source is present.
"""

from __future__ import annotations

from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from run_readonly_audit import (  # noqa: E402
    TESTED_BROWSER_PRODUCT_HEAD,
    TESTED_QA_SOURCE_HEAD,
    FR_IDS,
    NFR_IDS,
    ROOT,
    US_IDS,
    audit,
    broken_local_links,
    documented_routes,
    requirement_inventory,
    required_frontend_surfaces,
    route_decorators,
    stale_current_claims,
    adversarial_category_inventory,
    traceability_requirement_gaps,
    traceability_source_gaps,
)


def test_tested_source_identities_and_route_contract_crosswalk() -> None:
    report = audit()
    assert report["authority"]["tested_qa_source_head"] == TESTED_QA_SOURCE_HEAD
    assert report["authority"]["tested_browser_product_head"] == TESTED_BROWSER_PRODUCT_HEAD
    assert report["authority"]["artifact_context_head"]
    assert report["authority"]["browser_execution"] == "EXECUTED_ON_SEPARATELY_PINNED_PRODUCT_SOURCE"
    assert report["structural"]["route_mismatch"] == {
        "documented_not_implemented": [],
        "implemented_not_documented": [],
    }
    assert len(documented_routes()) == len(route_decorators()) == 26


def test_numbered_requirements_and_traceability_are_complete() -> None:
    inventory = requirement_inventory()
    assert inventory["expected"] == {"FR": len(FR_IDS), "NFR": len(NFR_IDS), "US": len(US_IDS)}
    assert inventory["observed"] == inventory["expected"]
    assert inventory["sequences_match"]
    assert inventory["traceability_complete"]
    rows = traceability_requirement_gaps()
    assert rows["expected_rows"] == 36
    assert rows["observed_rows"] == 36
    assert rows["complete"]
    assert traceability_source_gaps() == []


def test_local_markdown_links_and_required_routes_are_present() -> None:
    assert broken_local_links() == []
    surfaces = required_frontend_surfaces()
    assert surfaces["complete"]
    assert surfaces["expected_page_files"] == 13
    assert surfaces["actual_page_files"] == 13


def test_adversarial_test_categories_are_present() -> None:
    categories = adversarial_category_inventory()
    assert categories["expected"] == 22
    assert categories["present"] == 22
    assert categories["missing"] == {}
    assert categories["complete"]


def test_reconciled_current_contracts_have_no_drift() -> None:
    findings = stale_current_claims()
    assert findings == []
    assert audit()["status"] == "PASS"


def test_audit_has_no_write_or_browser_side_effects() -> None:
    # The audit is deliberately source-only.  This check documents the
    # allowed artifact boundary for reviewers and catches accidental expansion
    # of the test's own scope without coupling the artifact to a temporary
    # worktree name.
    assert ROOT == HERE.parents[2]
    assert (ROOT / "tests/adversarial/audit/run_readonly_audit.py").is_file()
    assert HERE.is_dir()
