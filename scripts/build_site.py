#!/usr/bin/env python3
"""Retired legacy site generator.

The former generator rendered stale H61-M/H61-G pages from older run cards,
including prohibited organizer-band-15 claims. The current documentation is
checked-in static HTML and is validated (not regenerated) by
``scripts/check_site.py`` and the Pages workflow. This compatibility shim fails
closed rather than overwriting the current evidence-backed site.
"""
from __future__ import annotations


def main() -> int:
    raise SystemExit(
        "Retired: refusing to regenerate docs from legacy run cards. "
        "Edit the current static pages and run scripts/check_site.py instead."
    )


if __name__ == "__main__":
    main()
