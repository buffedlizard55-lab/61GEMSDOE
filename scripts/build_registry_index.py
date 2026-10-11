#!/usr/bin/env python3
"""Build a hash-pinned, fail-closed index of accessible prior prediction rasters.

The index covers exactly the owner-repository/path list in
``scripts/registry_sources.tsv`` plus raster artifacts already published in
``docs/downloads``. It does not claim completeness for private, unlisted, or
organizer-side submissions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import rasterio

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "scripts" / "registry_sources.tsv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_sources() -> list[tuple[str, str]]:
    rows = []
    for line in SOURCES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"invalid registry source row: {line!r}")
        rows.append((parts[0], parts[1]))
    if len(set(rows)) != len(rows):
        raise ValueError("duplicate owner-repository/path record in registry_sources.tsv")
    return rows


def raster_record(path: Path, *, scope: str, sources: list[str], expected_grid=None) -> dict:
    record = dict(
        file=path.name,
        cache_file=str(path.resolve()),
        repo_relative_path=str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else None,
        scope=scope,
        sources=sources,
        bytes=path.stat().st_size,
        sha256=sha256(path),
    )
    try:
        with rasterio.open(path) as ds:
            record.update(
                count=ds.count,
                shape=[ds.height, ds.width],
                crs=str(ds.crs),
                transform=list(ds.transform)[:6],
                dtype=ds.dtypes[0] if ds.count else None,
            )
            if ds.count != 1:
                raise ValueError(f"expected one band, found {ds.count}")
            if expected_grid is not None:
                shape, crs, transform = expected_grid
                if ds.shape != tuple(shape):
                    raise ValueError(f"shape {ds.shape} != expected {tuple(shape)}")
                if ds.crs != crs:
                    raise ValueError(f"CRS {ds.crs} != expected {crs}")
                if ds.transform != transform:
                    raise ValueError("affine transform differs from the competition grid")
        record["grid_ok"] = True
    except Exception as exc:  # inventory failures must be recorded, not skipped
        record["grid_ok"] = False
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--public-cache", type=Path, default=Path("/tmp/refs/registry"))
    ap.add_argument("--local-root", type=Path, default=Path("docs/downloads"))
    ap.add_argument("--sample", type=Path, default=Path("data/official/sample_submission.tif"))
    ap.add_argument("--output", type=Path, default=Path("evidence/registry_accessible_index.json"))
    a = ap.parse_args()
    public_cache = a.public_cache if a.public_cache.is_absolute() else ROOT / a.public_cache
    local_root = a.local_root if a.local_root.is_absolute() else ROOT / a.local_root
    sample = a.sample if a.sample.is_absolute() else ROOT / a.sample
    output = a.output if a.output.is_absolute() else ROOT / a.output

    with rasterio.open(sample) as ds:
        expected_grid = (ds.shape, ds.crs, ds.transform)

    errors: list[dict] = []
    rasters: list[dict] = []
    sources = read_sources()
    fetched = 0
    for repo, repo_path in sources:
        cache_path = public_cache / Path(repo_path).name
        if not cache_path.is_file():
            errors.append(dict(source=f"{repo}:{repo_path}", error=f"missing cache file: {cache_path}"))
            rasters.append(dict(file=cache_path.name, cache_file=str(cache_path), scope="declared-public-owner-list",
                                sources=[f"{repo}:{repo_path}"], grid_ok=False, error="missing cache file"))
            continue
        row = raster_record(cache_path, scope="declared-public-owner-list",
                            sources=[f"{repo}:{repo_path}"], expected_grid=expected_grid)
        row["owner_repository"] = repo
        row["owner_path"] = repo_path
        if not row["grid_ok"]:
            errors.append(dict(source=f"{repo}:{repo_path}", error=row["error"]))
        fetched += 1
        rasters.append(row)

    local_files = sorted({*local_root.rglob("*.tif"), *local_root.rglob("*.tiff")}) if local_root.exists() else []
    for path in local_files:
        row = raster_record(path, scope="repository-prior-downloads",
                            sources=[path.relative_to(ROOT).as_posix()], expected_grid=expected_grid)
        if not row["grid_ok"]:
            errors.append(dict(source=path.relative_to(ROOT).as_posix(), error=row["error"]))
        rasters.append(row)

    expected_count = len(sources) + len(local_files)
    scope_complete = (fetched == len(sources) and not errors and len(rasters) == expected_count)
    report = dict(
        schema="gems61-accessible-raster-index-v1",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        declared_scope_complete=bool(scope_complete),
        organizer_registry_complete=False,
        completeness_note=("All paths explicitly declared in scripts/registry_sources.tsv and every TIFF in "
                           "docs/downloads were opened and matched to the pinned competition grid; this is not "
                           "the organizer-side registry and cannot include unlisted, private, or inaccessible files."),
        scope=dict(public_source_manifest="scripts/registry_sources.tsv",
                   declared_public_source_count=len(sources), fetched_public_source_count=fetched,
                   repository_prior_root=str(local_root), repository_prior_file_count=len(local_files),
                   total_raster_records=len(rasters)),
        grid=dict(shape=list(expected_grid[0]), crs=str(expected_grid[1]),
                  transform=list(expected_grid[2])[:6]),
        errors=errors,
        rasters=rasters,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(output=str(output), declared_scope_complete=scope_complete,
                          public_sources=f"{fetched}/{len(sources)}", local_priors=len(local_files),
                          raster_records=len(rasters), errors=len(errors)), indent=2))
    if not scope_complete:
        raise SystemExit("registry inventory is incomplete; uniqueness cannot be cleared")


if __name__ == "__main__":
    main()
