"""Regression checks for the published, fail-closed status pages."""
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CURRENT_PAGES = (
    "index.html",
    "executive-summary.html",
    "analysis.html",
    "hypotheses.html",
    "method.html",
    "holdout.html",
    "irregularities.html",
    "next-steps.html",
    "verify.html",
    "submit.html",
    "limitations.html",
)


class _HrefParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        if tag in {"a", "link"}:
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def test_current_status_pages_are_explicit_and_all_local_links_resolve():
    audit_top = json.loads((ROOT / "evidence/local_artifact_strict_dot_audit.json").read_text())
    audit_n = audit_top["summary"]["candidate_artifacts"]
    for name in CURRENT_PAGES:
        page = DOCS / name
        assert page.is_file(), f"missing generated page {name}"
        text = page.read_text(encoding="utf-8")
        parser = _HrefParser()
        parser.feed(text)
        for href in parser.hrefs:
            parsed = urlparse(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = (page.parent / unquote(parsed.path)).resolve()
            assert target.exists(), f"broken local link in {name}: {href}"

    for page in DOCS.glob("*.html"):
        if page.name in CURRENT_PAGES or page.name == "404.html":
            continue
        text = page.read_text(encoding="utf-8")
        assert "HISTORICAL PAGE — SUPERSEDED." in text, page.name
        assert 'href="index.html"' in text, page.name
        assert "../evidence/local_artifact_strict_dot_audit.json" in text, page.name
        assert f"strict audit blocks {audit_n}/{audit_n} local artifacts" in text, page.name

    index = (DOCS / "index.html").read_text(encoding="utf-8")
    executive = (DOCS / "executive-summary.html").read_text(encoding="utf-8")
    holdout = (DOCS / "holdout.html").read_text(encoding="utf-8")
    verify = (DOCS / "verify.html").read_text(encoding="utf-8")
    assert "NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION" in index
    assert "DO NOT SUBMIT" in executive
    assert "pre-placement surface-uniqueness receipt was found" in verify
    assert "current-run H61-L surface stopped before holdout" in holdout
    assert "HOLDOUT-DTI 0.044330" in holdout  # separate archived main-branch variant, not current run
    assert "HOLDOUT-DTI 0.060633" in holdout  # archived H61-MH, still proxy-only and not cleared
    assert "99.64000%" in holdout or "99.6400%" in holdout
    assert "351" in holdout and "215" in holdout
    assert f"{audit_n}/{audit_n}" in verify and "strict final-dot" in verify
    assert "99.1475%" in executive and "DO NOT SUBMIT" in executive
    assert "../evidence/h61l_run_card.json" in index

    card = json.loads((ROOT / "evidence/h61l_run_card.json").read_text())
    assert card["submission_decision"]["status"] == "DO NOT SUBMIT ANY FILE FROM THIS RUN"
    assert card["submission_decision"]["weekly_slot_used"] is False
    assert card["submission_decision"]["h61l_tiff_emitted"] is False
    assert len(card["review_passes"]) == 3
    assert all(item["result"] == "PASS" for item in card["review_passes"])

    inventory = json.loads((ROOT / "evidence/registry_accessible_index.json").read_text())
    assert inventory["declared_scope_complete"] is True
    assert inventory["organizer_registry_complete"] is False
    assert inventory["scope"]["declared_public_source_count"] == 21
    assert inventory["scope"]["repository_prior_file_count"] == 14
    assert inventory["scope"]["total_raster_records"] == 35
    assert set(inventory["scope"]["repository_prior_roots"]) == {
        "docs/downloads", "docs/submissions", "out"
    }
    assert any((row.get("repo_relative_path") or "").startswith("docs/submissions/")
               for row in inventory["rasters"])

    audit = json.loads((ROOT / "evidence/local_artifact_strict_dot_audit.json").read_text())
    assert audit["summary"]["candidate_artifacts"] == 12
    assert audit["summary"]["strict_overlap_stops"] == 12
    assert audit["summary"]["cleared_for_submission"] == 0
    mh = next(row for row in audit["candidates"]
              if any("gems61-h61m-invfeat-habitat" in path for path in row["paths"]))
    assert mh["one_sided_overlap_fraction"] == 0.9964
    assert mh["overlap_stop"] is True

    mh_card = json.loads((ROOT / "evidence/h61m_run_card.json").read_text())
    assert mh_card["current_submission_status"]["status"] == "DUPLICATE_LANE_DRIFT — NOT CLEARED"
    assert mh_card["correlation_overlap_vs_registry"]["legacy_policy_verdict"] == "UNIQUE"
    assert mh_card["correlation_overlap_vs_registry"]["verdict"].startswith("DUPLICATE_LANE_DRIFT")
    mh_receipt = json.loads((ROOT / "docs/downloads/gems61-h61m-invfeat-habitat-40000dots-20261011T062731Z-314697d7ff1f-zeros.json").read_text())
    assert mh_receipt["submission_allowed"] is False
    assert mh_receipt["strict_uniqueness"]["one_sided_overlap_fraction"] == 0.9964

    for report in ("FINAL_REPORT.md", "H61M_SUMMARY.md",
                   "IMPLEMENTATION_COMPLETE.md", "SESSION_SUMMARY.md"):
        text = (ROOT / report).read_text(encoding="utf-8")
        upper = text.upper()
        assert "HISTORICAL" in upper and "SUPERSEDED" in upper, report
        assert ("NO TIFF" in upper or "NO REPOSITORY TIFF" in upper), report
        assert "DO NOT SUBMIT" in upper, report
        assert "READY FOR SUBMISSION" not in upper, report


def test_h61g_surfaces_are_gated_before_holdout_even_for_direct_stage_calls():
    source = (ROOT / "scripts/run_h61g.py").read_text(encoding="utf-8")
    preflight = source[source.index("def _preflight_surface_fields"):source.index("def stage_holdout")]
    holdout = source[source.index("def stage_holdout"):source.index("def stage_final")]
    assert "gatesmod.lane_uniqueness_report" in preflight
    assert 'phase="surface"' in preflight
    assert "_preflight_surface_fields(fields, g)" in holdout
    assert holdout.index("_preflight_surface_fields(fields, g)") < holdout.index("holdoutmod.build_holdout")
    assert "if not eligible" in preflight and "do not run holdout" in preflight


def test_legacy_candidate_cli_entrypoints_fail_closed():
    retired = {
        "run_lane61.py": "incomplete local corpus",
        "run_lane61c.py": "partial corpus",
        "e2_build_candidate.py": "dense-reference/Jaccard",
        "build_candidate.py": "legacy candidate/holdout pipeline",
        "run_lane.py": "historical runner does not apply the current pre-placement",
        "make_submission.py": "legacy writer does not apply the complete-inventory strict",
        "e3_build_submission.py": "partial corpus and a base-rate enrichment",
        "write_submission.py": "may reuse a stale uniqueness receipt",
        "e2_holdout.py": "historical holdout runner bypasses the current strict",
        "e2c_canary.py": "current candidate failed pre-placement",
        "e2b_instrument.py": "historical instrument calibration compares HOLDOUT-DTI",
        "compare_top_arms.py": "do not score legacy candidate arms on another holdout",
        "run_experiment.py": "historical experiment suite bypasses the current strict",
        "run_h61mh.py": "archived TIFF fails strict final-dot uniqueness",
        "run_h61m.py": "runner retired: archived TIFF fails strict one-sided overlap",
        "make_h61m_submission.py": "writer retired: it must not write a new or submission-ready TIFF",
        "run_h61m2.py": "lineage budget was exceeded",
        "run_h61m3.py": "lineage budget was exceeded",
        "run_h61m4.py": "lineage budget was exceeded",
        "h61m_card.py": "legacy H61-MH UNIQUE claim",
    }
    for script, message in retired.items():
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--help"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        assert result.returncode != 0
        assert message in result.stdout + result.stderr


def test_h61m_legacy_site_builder_delegates_to_strict_status_builder():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_site_h61m.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "delegating to scripts/build_site_status.py" in result.stderr
    index = (DOCS / "index.html").read_text(encoding="utf-8")
    assert "NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION" in index
    assert "H61-MH" in index and "NOT CLEARED" in index
    assert "UNIQUE (safe to upload)" not in index
