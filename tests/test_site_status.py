"""Regression checks for the published, fail-closed status pages."""
from html.parser import HTMLParser
from pathlib import Path
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

    index = (DOCS / "index.html").read_text(encoding="utf-8")
    executive = (DOCS / "executive-summary.html").read_text(encoding="utf-8")
    holdout = (DOCS / "holdout.html").read_text(encoding="utf-8")
    verify = (DOCS / "verify.html").read_text(encoding="utf-8")
    assert "NO TIFF IS CURRENTLY CLEARED FOR COMPETITION SUBMISSION" in index
    assert "DO NOT SUBMIT" in executive
    assert "pre-placement surface-uniqueness receipt was found" in verify
    assert "H61-L HOLDOUT-DTI: NOT RUN" in holdout
    assert "351" in holdout and "215" in holdout
    assert "../evidence/h61l_run_card.json" in index
