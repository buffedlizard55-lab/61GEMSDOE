#!/usr/bin/env python3
"""Verify the built site before it is published.

Checks, in order:

1. every generated page exists and is non-trivial HTML;
2. every internal ``href`` resolves to a file that exists in ``docs/``;
3. every external link is https and points at a host this lane actually cited
   (an unexpected host is a hallucination risk and is reported as a failure);
4. no page still contains an unresolved placeholder;
5. the current run card and status banner agree: a denied submission decision
   must not be rendered as a cleared submission or an approved submission link.
   Explicit audit-only links remain allowed when their warning is visible.

Exit code 0 means the site is internally consistent.  It says nothing about
whether the evidence it quotes is correct -- that is what ``evidence/`` is for.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Hosts that appear in docs/data/sources.json or are standard infrastructure.
ALLOWED_HOSTS = {
    "www.drivendata.org", "community.drivendata.org", "doi.org",
    "pubs.geoscienceworld.org", "geophysics.geoscienceworld.org",
    "api.crossref.org", "store.usgs.gov", "pubs.usgs.gov",
    "www.energy.gov", "www.nlr.gov", "www.usgs.gov", "github.com", "raw.githubusercontent.com",
    "buffedlizard55-lab.github.io", "docs.nlr.gov", "www.crossref.org",
}

HREF = re.compile(r'href="([^"]+)"')
PLACEHOLDER = re.compile(r"\{\{|TODO|undefined|nan%|>nan<|None%")


def main() -> int:
    problems: list[str] = []
    # The current status pages are generated from the run card. Other merged
    # session pages remain available only as explicitly marked historical pages.
    from build_site import PAGES  # noqa: PLC0415
    pages = sorted(DOCS / name for name, _ in PAGES)
    if not pages:
        print("[site] FAIL: no html pages in docs/")
        return 1
    current_names = {p.name for p in pages}
    legacy_pages = sorted(p for p in DOCS.rglob("*.html")
                          if p.name not in current_names and p.name != "404.html")
    print(f"[site] {len(pages)} current pages, {len(legacy_pages)} legacy pages")
    for legacy in legacy_pages:
        text = legacy.read_text(encoding="utf-8")
        if "HISTORICAL PAGE — SUPERSEDED." not in text:
            problems.append(f"{legacy.relative_to(DOCS)}: legacy page lacks the superseded-status warning")
        if 'href="index.html"' not in text:
            problems.append(f"{legacy.relative_to(DOCS)}: legacy page does not link to current status")
        if '../evidence/local_artifact_strict_dot_audit.json' not in text:
            problems.append(f"{legacy.relative_to(DOCS)}: legacy page does not link to the strict artifact audit")

    for page in pages:
        text = page.read_text(encoding="utf-8")
        if len(text) < 400:
            problems.append(f"{page.name}: page is suspiciously short ({len(text)} bytes)")
        for m in PLACEHOLDER.finditer(text):
            problems.append(f"{page.name}: unresolved placeholder {m.group(0)!r}")
        for href in HREF.findall(text):
            if href.startswith("#") or href.startswith("mailto:"):
                continue
            if href.startswith("http://") or href.startswith("https://"):
                host = href.split("/")[2]
                if host not in ALLOWED_HOSTS:
                    problems.append(f"{page.name}: external host not in the cited set: {host}")
                if href.startswith("http://"):
                    problems.append(f"{page.name}: insecure link {href}")
                continue
            target = (page.parent / href.split("#")[0].split("?")[0]).resolve()
            if not target.exists():
                problems.append(f"{page.name}: broken internal link -> {href}")

    # the banner and the run card must agree
    import json
    card_path = ROOT / "evidence" / "h61l_run_card.json"
    index = DOCS / "index.html"
    if index.exists() and card_path.is_file():
        card = json.loads(card_path.read_text())
        decision = card.get("submission_decision", {})
        authorised = bool(decision.get("okay_to_submit", False))
        text = index.read_text()
        publishes_submission_link = "Download the submission GeoTIFF" in text
        claims_cleared = ("CLEARED —" in text or "YES — it is FORMAT-VALID and UNIQUE" in text)
        states_no_clearance = "NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION" in text
        if authorised and not publishes_submission_link:
            problems.append("current run card authorises submission but the page publishes no exact submission link")
        if not authorised and (publishes_submission_link or claims_cleared):
            problems.append("current run card does NOT authorise submission but the page claims a cleared file")
        if not authorised and not states_no_clearance:
            problems.append("current run card denies submission but the status page omits the no-clearance banner")
        print(f"[site] current run card okay_to_submit={authorised}, page claims cleared={claims_cleared}")
    elif index.exists():
        problems.append("index.html exists but the current evidence/h61l_run_card.json was not found")

    if problems:
        print(f"[site] FAIL ({len(problems)} problems)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[site] OK: pages, internal links, external hosts and the download gate are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
