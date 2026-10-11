#!/usr/bin/env python3
"""Verify the built site before it is published.

Checks, in order:

1. every generated page exists and is non-trivial HTML;
2. every internal ``href`` resolves to a file that exists in ``docs/``;
3. every external link is https and points at a host this lane actually cited
   (an unexpected host is a hallucination risk and is reported as a failure);
4. no page still contains an unresolved placeholder;
5. the download banner and the run card agree: if the card says the artifact is
   not authorised for download, the site must not publish a link to it.

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
    "www.energy.gov", "www.nlr.gov", "github.com", "raw.githubusercontent.com",
    "buffedlizard55-lab.github.io", "docs.nlr.gov", "www.crossref.org",
    # USGS The National Map downloader, cited in irregularity IR-61-SRC-01 as the
    # free official source for the 3DEP 1 m lidar hypothesis (H61-N).
    "apps.nationalmap.gov",
}

HREF = re.compile(r'href="([^"]+)"')
PLACEHOLDER = re.compile(r"\{\{|TODO|undefined|nan%|>nan<|None%")


def main() -> int:
    problems: list[str] = []
    # Only the pages this session's builder emits are in scope; pages written by
    # the parallel sessions that are merged on main are linked, not vetted here.
    from build_site import PAGES  # noqa: PLC0415
    pages = sorted(DOCS / name for name, _ in PAGES)
    if not pages:
        print("[site] FAIL: no html pages in docs/")
        return 1
    print(f"[site] {len(pages)} pages")

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

    # The banner and the run cards must agree.  Every card that declares
    # ``okay_to_download`` is enforced: if it says NO, index must not link its
    # raster; the NEWEST flagged card is the site's headline and index must
    # link it.  Cards without the flag pre-date the gate and are skipped.
    import json
    cards = []
    card_paths = sorted((ROOT / "evidence").glob("*run_card*.json")) + \
        sorted((DOCS / "data").glob("*run_card*.json"))
    for p in card_paths:
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(d, dict) and "okay_to_download" in d:
            cards.append((p, d))
    index = DOCS / "index.html"
    if index.exists() and cards:
        text = index.read_text()

        def linked(raster_file: str) -> bool:
            name = Path(raster_file).name
            return bool(name) and re.search(r'href="[^"]*' + re.escape(name), text) is not None

        for p, d in cards:
            raster = ((d.get("raster") or {}).get("file")) or ""
            if linked(raster) and not d.get("okay_to_download", False):
                problems.append(f"run card {p.name} does NOT authorise the download "
                                f"but index links {Path(raster).name}")
        newest_path, newest = max(cards, key=lambda t: t[0].stat().st_mtime)
        raster = ((newest.get("raster") or {}).get("file")) or ""
        authorised = bool(newest.get("okay_to_download", False))
        publishes_link = linked(raster)
        if authorised and not publishes_link:
            problems.append(f"newest run card {newest_path.name} authorises "
                            f"{Path(raster).name} but the page publishes no link")
        if not authorised and publishes_link:
            problems.append("run card does NOT authorise the download but the page publishes a link")
        print(f"[site] run-card gate: {len(cards)} flagged card(s); newest {newest_path.name} "
              f"okay_to_download={authorised}, page publishes link={publishes_link}")
    elif index.exists():
        problems.append("index.html exists but no run_card.json was found")

    if problems:
        print(f"[site] FAIL ({len(problems)} problems)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[site] OK: pages, internal links, external hosts and the download gate are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
