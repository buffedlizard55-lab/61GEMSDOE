#!/usr/bin/env python3
"""Validate the checked-in static site and its H61U download gate.

Every HTML page under docs/ is checked for local links and cited HTTPS hosts.
The current H61U card is the sole authority for whether its exact GeoTIFF may
be linked. A download permission is not a submission or weekly-slot approval.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

ALLOWED_HOSTS = {
    "www.drivendata.org", "community.drivendata.org", "doi.org",
    "pubs.geoscienceworld.org", "geophysics.geoscienceworld.org",
    "api.crossref.org", "store.usgs.gov", "pubs.usgs.gov", "www.usgs.gov",
    "www.energy.gov", "www.nlr.gov", "github.com", "raw.githubusercontent.com",
    "buffedlizard55-lab.github.io", "docs.nlr.gov", "www.crossref.org",
    "ngdc.noaa.gov", "www.ngdc.noaa.gov", "www.ncei.noaa.gov",
}
HREF = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
PLACEHOLDER = re.compile(r"\{\{|\bTODO\b|\bundefined\b|\bnan%|>nan<|None%")


def main() -> int:
    problems: list[str] = []
    pages = sorted(DOCS.rglob("*.html"))
    if not pages:
        print("[site] FAIL: no HTML pages under docs/")
        return 1
    print(f"[site] checking {len(pages)} HTML pages")

    for page in pages:
        try:
            text = page.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append(f"{page.relative_to(DOCS)}: cannot read: {exc}")
            continue
        if len(text) < 350:
            problems.append(f"{page.relative_to(DOCS)}: suspiciously short ({len(text)} bytes)")
        for match in PLACEHOLDER.finditer(text):
            problems.append(f"{page.relative_to(DOCS)}: unresolved placeholder {match.group(0)!r}")
        for href in HREF.findall(text):
            if href.startswith(("#", "mailto:", "javascript:")):
                continue
            parts = urlsplit(href)
            if parts.scheme:
                if parts.scheme != "https":
                    problems.append(f"{page.relative_to(DOCS)}: insecure/unsupported link {href}")
                elif (parts.hostname or "").lower() not in ALLOWED_HOSTS:
                    problems.append(f"{page.relative_to(DOCS)}: uncited external host: {parts.hostname}")
                continue
            target = (page.parent / parts.path).resolve()
            if not target.exists():
                problems.append(f"{page.relative_to(DOCS)}: broken local link -> {href}")

    card_path = ROOT / "evidence" / "h61u_run_card.json"
    index_path = DOCS / "index.html"
    if not card_path.is_file():
        problems.append("evidence/h61u_run_card.json is missing; current download state cannot be verified")
    elif not index_path.is_file():
        problems.append("docs/index.html is missing")
    else:
        card = json.loads(card_path.read_text(encoding="utf-8"))
        sub = card.get("submission") or {}
        raster = card.get("raster") or {}
        authorized = str(sub.get("download_permission", "")).startswith("OK_TO_DOWNLOAD")
        artifact_links_by_page = {
            page.relative_to(DOCS).as_posix(): [
                h for h in HREF.findall(page.read_text(encoding="utf-8"))
                if Path(urlsplit(h).path).suffix.lower() in {".tif", ".tiff", ".zip"}
            ]
            for page in pages
        }
        index_artifacts = artifact_links_by_page["index.html"]
        candidate_rel = str(raster.get("path") or "")
        candidate_path = (ROOT / candidate_rel).resolve() if candidate_rel else None
        candidate_name = Path(candidate_rel).name if candidate_rel else ""
        candidate_link = any(
            not urlsplit(h).scheme and (DOCS / urlsplit(h).path).resolve() == candidate_path
            for h in index_artifacts
        )
        all_artifact_links = [(name, href) for name, hrefs in artifact_links_by_page.items() for href in hrefs]
        tif_links = [(name, href) for name, href in all_artifact_links
                     if Path(urlsplit(href).path).suffix.lower() in {".tif", ".tiff"}]
        zip_links = [(name, href) for name, href in all_artifact_links
                     if Path(urlsplit(href).path).suffix.lower() == ".zip"]
        if authorized:
            if not candidate_link:
                problems.append("H61U card authorises download but index does not link its exact TIF")
            if len(tif_links) != 1 or not candidate_link:
                problems.append("authorized site must expose exactly one TIF link, to the current candidate")
            expected_zip_stem = Path(candidate_name).stem if candidate_name else ""
            if len(zip_links) > 1 or any(Path(urlsplit(href).path).stem != expected_zip_stem
                                         for _, href in zip_links):
                problems.append("authorized site may only link the matching current-candidate ZIP")
            if len(all_artifact_links) != len(tif_links) + len(zip_links):
                problems.append("artifact link classification is inconsistent")
            if not candidate_rel or not (ROOT / candidate_rel).is_file():
                problems.append("H61U card authorises download but its raster path is missing")
            if not raster.get("sha256"):
                problems.append("H61U card authorises download but has no raster SHA-256")
            if not (card.get("format_validator") or {}).get("all_passed", False):
                problems.append("H61U card authorises download without a passing independent format validator")
            if not (card.get("uniqueness_decision") or {}).get("final_pass", False):
                problems.append("H61U card authorises download without a passing final-dot uniqueness result")
        else:
            if all_artifact_links:
                problems.append("site links one or more TIFF/ZIP artifacts although the current run card grants no download permission")
            if raster.get("path") or raster.get("sha256") or card.get("candidate_tif_created"):
                problems.append("current run card has candidate artifact fields despite withholding download permission")
        print(f"[site] H61U okay_to_download={authorized}; current artifact links={len(all_artifact_links)}; "
              f"submit recommendation={sub.get('submit_recommendation', 'not recorded')}; "
              f"weekly slot approved={sub.get('weekly_slot_approved', False)}")

    if problems:
        print(f"[site] FAIL ({len(problems)} problems)")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("[site] OK: HTML, local links, HTTPS hosts and H61U download gate are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
