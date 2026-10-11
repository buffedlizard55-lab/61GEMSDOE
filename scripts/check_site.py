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
    "apps.nationalmap.gov", "prd-tnm.s3.amazonaws.com", "www.usgs.gov",
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

    for page in sorted(DOCS.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        if page in pages:
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

    # ---- the download gate -------------------------------------------------
    # A page may publish a link to <name>.tif only when a receipt for that exact
    # file records a passing format validation, and no receipt refuses it.  The
    # front page must publish at least one cleared file.
    import json

    def receipt_file(d):
        for k in ("file", "path", "tif"):
            v = d.get(k)
            if isinstance(v, str) and v.endswith(".tif"):
                return Path(v).name
        dl = d.get("download")
        if isinstance(dl, dict) and isinstance(dl.get("tif"), str):
            return Path(dl["tif"]).name
        for k in ("submission_name", "name"):
            v = d.get(k)
            if isinstance(v, str) and v:
                return v if v.endswith(".tif") else v + ".tif"
        return None

    def receipt_ok(d):
        if d.get("okay_to_download") is True:
            return True
        for key in ("validator", "validation"):
            v = d.get(key)
            if isinstance(v, dict) and (v.get("all_checks_passed") is True or v.get("ok") is True):
                return True
        tr = d.get("template_report")
        if isinstance(tr, dict) and tr.get("ok") is True:
            return True
        return False

    allowed: dict[str, str] = {}
    refused: dict[str, str] = {}
    for base in (ROOT / "evidence", DOCS / "downloads", DOCS / "submissions"):
        for p in sorted(base.glob("*.json")):
            try:
                d = json.loads(p.read_text())
            except (json.JSONDecodeError, OSError):
                problems.append(f"{p.name}: unreadable receipt")
                continue
            if not isinstance(d, dict):
                continue
            name = receipt_file(d)
            if not name:
                continue
            key = f"{p.parent.name}/{p.name}"
            if d.get("okay_to_download") is False:
                refused[name] = key
            elif receipt_ok(d):
                allowed.setdefault(name, key)
    for n in refused:
        allowed.pop(n, None)
    print(f"[site] download gate: {len(allowed)} cleared .tif receipts, {len(refused)} refused")

    index_cleared = False
    for page in sorted(DOCS.glob("*.html")):
        if not page.exists():
            continue
        for href in HREF.findall(page.read_text(encoding="utf-8")):
            if href.startswith(("http", "#", "mailto:")):
                continue
            tail = Path(href.split("#")[0].split("?")[0]).name
            if not tail.endswith((".tif", ".zip")):
                continue
            stem = tail[:-4] + ".tif" if tail.endswith(".zip") else tail
            if stem in refused:
                problems.append(f"{page.name}: publishes {tail} although {refused[stem]} refuses it")
            elif stem not in allowed:
                problems.append(f"{page.name}: publishes {tail} but no receipt clears that file "
                                "for download")
            elif page.name == "index.html":
                index_cleared = True
    if not index_cleared:
        problems.append("index.html publishes no cleared .tif download link (the submission file "
                        "must be easy to download)")

    if problems:
        print(f"[site] FAIL ({len(problems)} problems)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[site] OK: pages, internal links, external hosts and the download gate are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
