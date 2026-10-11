#!/usr/bin/env python3
"""Short-circuit strict final-dot audits of repository-local TIFF artifacts.

The literal gate stops at the first prior raster whose one-sided candidate
support overlap exceeds 70%. This audit uses the known dense basement-HGM
raster as a sufficient stop comparator for each local artifact; it does not
claim that non-failing candidates passed the full rank-correlation gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ROOTS = (Path("docs/downloads"), Path("docs/submissions"), Path("out"))
DEFAULT_REFERENCE = Path(
    "docs/downloads/gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def local_tiffs() -> list[Path]:
    found = {}
    for root in LOCAL_ROOTS:
        directory = ROOT / root
        if directory.exists():
            for pattern in ("*.tif", "*.tiff"):
                for path in directory.rglob(pattern):
                    found[path.resolve()] = path
    return [found[key] for key in sorted(found)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=Path("evidence/registry_accessible_index.json"))
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--sample", type=Path, default=Path("data/official/sample_submission.tif"))
    parser.add_argument("--output", type=Path, default=Path("evidence/local_artifact_strict_dot_audit.json"))
    args = parser.parse_args()

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path

    inventory_path, reference_path, sample_path, output_path = map(
        resolve, (args.inventory, args.reference, args.sample, args.output)
    )
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    from gems61.uniqueness import dot_overlap

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not inventory.get("declared_scope_complete") or inventory.get("errors"):
        raise SystemExit("refusing audit against incomplete declared inventory")

    with rasterio.open(sample_path) as sample:
        expected_shape, expected_crs, expected_transform = (
            sample.shape, sample.crs, sample.transform
        )
    reference_record = next(
        (row for row in inventory.get("rasters", [])
         if row.get("repo_relative_path") == reference_path.relative_to(ROOT).as_posix()),
        None,
    )
    if reference_record is None:
        raise SystemExit("stop comparator is absent from the indexed inventory")
    if sha256(reference_path) != reference_record.get("sha256"):
        raise SystemExit("stop comparator hash differs from the index pin")
    with rasterio.open(reference_path) as src:
        if (src.count != 1 or src.shape != expected_shape or src.crs != expected_crs
                or src.transform != expected_transform):
            raise SystemExit("stop comparator differs from the pinned competition grid")
        reference_values = src.read(1)
    with rasterio.open(sample_path) as sample:
        template = sample.read(1)
        # The competition template uses finite values for scored cells and NaN
        # outside. This is the same pixel-exact footprint consumed by the shared
        # gate's grid loader, without deriving anything from a candidate.
        footprint = np.isfinite(template)
    if footprint.shape != expected_shape:
        raise SystemExit("sample footprint shape mismatch")
    reference_positive = (np.isfinite(reference_values) & (reference_values > 0)
                          & footprint)
    if not reference_positive.any():
        raise SystemExit("stop comparator has no positive support")
    reference_coverage = dot_overlap(
        footprint.astype(np.float32), reference_values, footprint=footprint
    )

    # Group byte-identical copies so an output mirrored into downloads/submissions
    # is not counted as a distinct candidate artifact.
    grouped: dict[str, list[Path]] = {}
    indexed_by_path = {
        row.get("repo_relative_path"): row
        for row in inventory.get("rasters", [])
        if isinstance(row, dict) and row.get("repo_relative_path")
    }
    for path in local_tiffs():
        if path.resolve() == reference_path.resolve():
            continue
        relative = path.relative_to(ROOT).as_posix()
        record = indexed_by_path.get(relative)
        if record is None:
            raise SystemExit(f"local raster is absent from the index: {relative}")
        digest = sha256(path)
        if digest != record.get("sha256"):
            raise SystemExit(f"local raster hash differs from the index pin: {relative}")
        grouped.setdefault(digest, []).append(path)

    candidates = []
    for digest, copies in sorted(grouped.items()):
        path = sorted(copies)[0]
        with rasterio.open(path) as src:
            if (src.count != 1 or src.shape != expected_shape or src.crs != expected_crs
                    or src.transform != expected_transform):
                raise SystemExit(f"candidate is off-grid: {path.relative_to(ROOT)}")
            values = src.read(1)
        if not np.isfinite(values[footprint]).all():
            raise SystemExit(f"candidate has non-finite values inside footprint: {path.relative_to(ROOT)}")
        support = (values > 0) & footprint
        n_positive = int(support.sum())
        fraction = dot_overlap(values, reference_values, px=3, footprint=footprint)
        n_within = int(round(fraction * n_positive))
        stopped = fraction > 0.70
        candidates.append(dict(
            paths=[p.relative_to(ROOT).as_posix() for p in sorted(copies)],
            sha256=digest,
            positive_pixels=n_positive,
            comparator=reference_path.relative_to(ROOT).as_posix(),
            comparator_sha256=reference_record["sha256"],
            comparator_positive_pixels=int(reference_positive.sum()),
            comparator_footprint_coverage_within_3px=reference_coverage,
            candidate_positive_pixels_within_3px=n_within,
            one_sided_overlap_fraction=fraction,
            one_sided_overlap_percent=100.0 * fraction,
            overlap_stop=stopped,
            verdict="DUPLICATE_LANE_DRIFT" if stopped else "NOT_CLEARED",
            rank_correlation=(
                "NOT_EVALUATED — overlap already exceeds the strict stop threshold"
                if stopped else
                "NOT_EVALUATED — this targeted audit does not clear a candidate"
            ),
            preplacement_surface_gate="NOT_RECORDED_FOR_THIS_ARCHIVED_OUTPUT",
            cleared_for_submission=False,
        ))

    report = dict(
        schema="gems61-local-artifact-strict-dot-audit-v1",
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        evidence_class="MEASURED final-raster one-sided overlap audit; not an organizer receipt",
        policy=dict(
            support="every finite value strictly >0 inside the scored footprint",
            distance="Euclidean distance transform; candidate positive cell within <=3 grid cells",
            stop="one-sided candidate-support overlap >0.70 against any one prior raster; no Jaccard/density/base-rate exception",
            rank_correlation="not calculated after a strict overlap stop; correlation cannot reverse a failing overlap result",
        ),
        inventory=dict(
            path=inventory_path.relative_to(ROOT).as_posix(),
            sha256=sha256(inventory_path),
            declared_scope_complete=inventory["declared_scope_complete"],
            organizer_registry_complete=inventory.get("organizer_registry_complete", False),
            declared_public_sources=inventory["scope"]["declared_public_source_count"],
            local_prior_tiffs=inventory["scope"]["repository_prior_file_count"],
            indexed_records=inventory["scope"]["total_raster_records"],
            roots=inventory["scope"].get("repository_prior_roots", []),
        ),
        comparator=dict(
            path=reference_path.relative_to(ROOT).as_posix(),
            sha256=reference_record["sha256"],
            positive_pixels=int(reference_positive.sum()),
            footprint_coverage_within_3px=reference_coverage,
        ),
        execution_note=(
            "The comparator already breaches the literal one-sided overlap stop for every listed local candidate. "
            "The gate therefore stops on that measured failure; no Jaccard exception, holdout, or submission clearance is inferred. "
            "These post-placement checks do not replace a required pre-placement surface gate."
        ),
        summary=dict(
            candidate_artifacts=len(candidates),
            strict_overlap_stops=sum(row["overlap_stop"] for row in candidates),
            cleared_for_submission=0,
            holdout_reached=0,
        ),
        candidates=candidates,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    for row in candidates:
        print(f"{row['one_sided_overlap_fraction']:.6%}\t{', '.join(row['paths'])}")


if __name__ == "__main__":
    main()
