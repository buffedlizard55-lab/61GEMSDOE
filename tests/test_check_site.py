"""The static-site artifact links must match the current run-card authority."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_site  # noqa: E402


def _site(root: Path, *, authorized: bool, href: str | None = None) -> None:
    docs = root / "docs"
    downloads = docs / "downloads"
    submissions = docs / "submissions"
    evidence = root / "evidence"
    downloads.mkdir(parents=True)
    submissions.mkdir(parents=True)
    evidence.mkdir()

    candidate_path = "docs/downloads/current.tif" if authorized else None
    if authorized:
        (root / candidate_path).write_bytes(b"current candidate")
    if href == "submissions/current.tif":
        (submissions / "current.tif").write_bytes(b"wrong file with same basename")
    anchor = f'<a href="{href}">artifact</a>' if href else "No artifact link."
    (docs / "index.html").write_text(
        "<!doctype html><html><body>" + anchor + " " + ("content " * 60) + "</body></html>",
        encoding="utf-8",
    )
    card = {
        "submission": {
            "download_permission": "OK_TO_DOWNLOAD" if authorized else "NO_CANDIDATE_ARTIFACT",
            "submit_recommendation": "NOT_RECOMMENDED",
            "weekly_slot_approved": False,
        },
        "raster": {
            "path": candidate_path,
            "sha256": "abc123" if authorized else None,
        },
        "candidate_tif_created": authorized,
        "format_validator": {"all_passed": authorized},
        "uniqueness_decision": {"final_pass": authorized},
    }
    (evidence / "h61u_run_card.json").write_text(json.dumps(card), encoding="utf-8")

def test_denied_run_has_no_artifact_link(tmp_path, monkeypatch):
    _site(tmp_path, authorized=False)
    monkeypatch.setattr(check_site, "ROOT", tmp_path)
    monkeypatch.setattr(check_site, "DOCS", tmp_path / "docs")
    assert check_site.main() == 0


def test_authorized_run_links_exact_current_candidate(tmp_path, monkeypatch):
    _site(tmp_path, authorized=True, href="downloads/current.tif")
    monkeypatch.setattr(check_site, "ROOT", tmp_path)
    monkeypatch.setattr(check_site, "DOCS", tmp_path / "docs")
    assert check_site.main() == 0


def test_authorized_run_rejects_same_basename_in_another_directory(tmp_path, monkeypatch):
    _site(tmp_path, authorized=True, href="submissions/current.tif")
    monkeypatch.setattr(check_site, "ROOT", tmp_path)
    monkeypatch.setattr(check_site, "DOCS", tmp_path / "docs")
    assert check_site.main() == 1
