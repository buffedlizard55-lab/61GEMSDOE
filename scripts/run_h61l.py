#!/usr/bin/env python3
"""H61-L: public USGS 3DEP scarp descriptors inside buried basement-step corridors.

The raw candidate surface is checked against the declared raster inventory BEFORE
any placement. A literal duplicate/overlap stop terminates the run: no holdout,
GeoTIFF, or submission-ready claim is produced. If that gate passes, the script
uses the shared buffered hide-and-recover folds/evaluator and submission writer.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import buried as B  # noqa: E402
from gems61 import evaluate_holdout as evaluator  # noqa: E402
from gems61 import gates  # noqa: E402
from gems61 import grid as gridmod  # noqa: E402
from gems61 import h61g as H  # noqa: E402
from gems61 import holdout_segmented as holdoutmod  # noqa: E402
from gems61 import metric  # noqa: E402
from gems61 import network  # noqa: E402
from gems61 import submission_writer  # noqa: E402

EVID = ROOT / "evidence"
OUT = ROOT / "out"
DOWNLOADS = ROOT / "docs" / "downloads"
CACHE = ROOT / ".cache" / "h61g"
LIDAR = ROOT / ".cache" / "external" / "lidar_scarp_features_u8.tif"
LIDAR_JSON = ROOT / "evidence" / "h61l_lidar_source.json"
INDEX = EVID / "registry_accessible_index.json"
EXPECTED_LIDAR_SHA256 = "d580bb8bdcdb941e32fefb8b38044bc5bf04e199bf2e83498c3576e6fc465568"
UPSTREAM = "https://github.com/buffedlizard55-lab/GEMSDOE24/blob/main/data/external/lidar_scarp_features_u8.tif"
UPSTREAM_META = "https://github.com/buffedlizard55-lab/GEMSDOE24/blob/main/data/external/lidar_scarp_features.json"
UPSTREAM_COMMIT = "2e7bf080270493f77286fd62f2db958805053ba5"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _jsonable(value):
    if isinstance(value, np.ndarray):
        return _jsonable(value.tolist())
    if isinstance(value, (np.floating,)):
        value = float(value)
    elif isinstance(value, (np.integer,)):
        return int(value)
    elif isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def write_json(name: str, obj) -> Path:
    EVID.mkdir(parents=True, exist_ok=True)
    path = EVID / name
    path.write_text(json.dumps(_jsonable(obj), indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}", flush=True)
    return path


def _decode_quantized(q: np.ndarray, xmax: float, mode: str) -> np.ndarray:
    """Invert the upstream q=1+round(254*t(x/xmax)) encoding; 0 means no data."""
    q = np.asarray(q, np.float32)
    t = np.clip((q - 1.0) / 254.0, 0.0, 1.0)
    if mode == "sqrt":
        unit = t * t
    elif mode == "linear":
        unit = t
    else:
        raise ValueError(f"unknown quantization mode: {mode}")
    return np.where(q > 0, unit * np.float32(xmax), 0.0).astype(np.float32)


def _record_lidar_provenance() -> dict:
    if not LIDAR.is_file():
        raise FileNotFoundError(
            f"missing pinned public lidar descriptor {LIDAR}; check availability at {UPSTREAM} "
            "and fetch the blob only through the repository's GitHub/API path"
        )
    digest = sha256_file(LIDAR)
    if digest != EXPECTED_LIDAR_SHA256:
        raise ValueError(f"lidar descriptor SHA-256 mismatch: {digest}")
    with rasterio.open(LIDAR) as src:
        record = dict(
            source=UPSTREAM,
            metadata_source=UPSTREAM_META,
            upstream_repository="buffedlizard55-lab/GEMSDOE24",
            upstream_commit=UPSTREAM_COMMIT,
            upstream_git_blob_sha="da733b53147efad5c141ffdb96e469ec5b4da8b8",
            local_sha256=digest,
            bytes=LIDAR.stat().st_size,
            shape=[src.height, src.width],
            count=src.count,
            dtype=list(src.dtypes),
            crs=str(src.crs),
            transform=list(src.transform)[:6],
            nodata=src.nodata,
            bands=list(src.descriptions),
            method_note=("Twelve uint8 terrain-descriptor channels aggregated from 2 m work cells; "
                         "upstream metadata identifies USGS 3DEP 1 m DEM tiles. Quantized descriptors "
                         "are not fault labels or a fault-detection raster."),
            rights_note=("Upstream metadata states USGS 3DEP products are available without use restrictions; "
                         "the source feature file is a public sibling-repository derivative."),
            caveats=[
                "uncalibrated terrain descriptors, not fault detections",
                "roads, channels, terrace risers, paleo-shorelines, landslides and mines also create steps",
                "upstream metadata reports 10 failed tiles out of 716 and approximately 1-2 m datum offset",
                "source is a sibling feature product; no sibling prediction raster is used",
            ],
            label="PUBLIC-REPOSITORY-DERIVATIVE; not organizer-provided and not an organizer score receipt",
        )
    write_json("h61l_lidar_source.json", record)
    return record


def _build_surface(g):
    """Create one preregistered scarp-ribbon surface from cached basement depth + lidar."""
    needed = ["depth_full.npy", "steps_full.npy", "hgm_full.npy", "throw_full.npy"]
    missing = [name for name in needed if not (CACHE / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing cached inversion arrays {missing}; run scripts/run_h61g.py invert once")

    depth = np.load(CACHE / "depth_full.npy", mmap_mode="r").astype(np.float32)
    steps = np.load(CACHE / "steps_full.npy", mmap_mode="r").astype(bool)
    hgm = np.load(CACHE / "hgm_full.npy", mmap_mode="r").astype(np.float32)
    throw = np.load(CACHE / "throw_full.npy", mmap_mode="r").astype(np.float32)
    if any(a.shape != g.shape for a in (depth, steps, hgm, throw)):
        raise ValueError("cached basement surfaces differ from the competition grid")
    valid = g.footprint & np.isfinite(depth)
    corridor = H.corridor_mask(steps, H.CORRIDOR_PX)
    basin = valid & (depth > H.BASIN_FLOOR_M)
    working = valid & corridor & basin
    concealment = B.concealment_prior(depth, floor_m=H.BASIN_FLOOR_M, cap_m=1500.0)

    # Decode the documented upstream 12-band feature file. Bands are 1-based:
    # 1 ex_max, 3 step_max, 4 lapneg_max, 5 lappos_max, 10 coh100, 12 valid.
    with rasterio.open(LIDAR) as src:
        if src.count != 12 or src.shape != g.shape:
            raise ValueError(f"lidar feature grid/count mismatch: {src.shape}, {src.count}")
        with rasterio.open(gridmod.DATA_DIR / "sample_submission.tif") as sample:
            if src.crs != sample.crs or src.transform != sample.transform:
                raise ValueError("lidar feature CRS/transform differs from the pinned competition template")
        if tuple(src.descriptions) != ("ex_max", "ex_mean", "step_max", "lapneg_max",
                                      "lappos_max", "downface_max", "upface_max", "cross_max",
                                      "relief", "coh100", "strike", "valid"):
            raise ValueError(f"unexpected lidar feature band descriptions: {src.descriptions}")
        valid_fraction = _decode_quantized(src.read(12), 1.0, "linear")
        ex = _decode_quantized(src.read(1), 1.5, "sqrt") / 1.5
        step = _decode_quantized(src.read(3), 1.0, "sqrt")
        crest = _decode_quantized(src.read(4), 0.05, "sqrt") / 0.05
        base = _decode_quantized(src.read(5), 0.05, "sqrt") / 0.05
        coherence = _decode_quantized(src.read(10), 1.0, "linear")

    lidar_valid = valid_fraction > 0.0
    # A scarp-like signature requires short-wavelength steepness, a sharp 10 m vs
    # 50 m slope break, a convex crest + concave base, and coherent linear form.
    # No catalogue values or hidden labels enter this feature surface.
    scarp = np.sqrt(np.clip(ex * step, 0.0, 1.0))
    scarp *= np.sqrt(np.clip(crest * base, 0.0, 1.0))
    scarp *= np.clip(coherence, 0.0, 1.0)
    scarp[~lidar_valid] = 0.0
    scarp[~g.footprint] = 0.0

    # Restrict the lidar locator to mapped basement-step corridors under basin fill;
    # then emit three-cell-wide multi-line ribbons, not a set of isolated dots.
    ridges = B.blakely_simpson_maxima(scarp) & (scarp > 0.0) & working & lidar_valid
    ribbon = H.ribbon(ridges, 1) & working & lidar_valid
    ridge_strength = ndi.maximum_filter(scarp, size=3, mode="nearest")
    field = (ribbon.astype(np.float32) * ridge_strength *
             (0.3 + 0.7 * concealment.astype(np.float32)))
    field = np.where(working, field, 0.0).astype(np.float32)
    field[~np.isfinite(field)] = 0.0
    if field.min() < 0 or field.max() > 1:
        raise ValueError("candidate scarp surface escaped [0,1]")

    features = {
        "inverted basement depth": np.where(valid, depth, 0.0).astype(np.float32),
        "basement depth HGM": np.where(valid, hgm, 0.0).astype(np.float32),
        "minimum step throw": np.where(valid, throw, 0.0).astype(np.float32),
        "lidar shortwave excess slope": ex,
        "lidar sharp step": step,
        "lidar convex crest": crest,
        "lidar concave base": base,
        "lidar structure-tensor coherence": coherence,
        "composite lidar scarp score": scarp,
        "gravity-step corridor": corridor.astype(np.float32),
        "basin interior": basin.astype(np.float32),
    }
    meta = dict(
        candidate="H61-L: USGS 3DEP scarp-score maxima, emitted as 3-cell ribbons inside a basement-step corridor",
        method="sqrt(ex_max_norm*step_max_norm) * sqrt(lapneg_max_norm*lappos_max_norm) * coh100; "
               "local maxima; 3-cell ribbon; inverted depth > 100 m; within +/-1 km of >=80 m basement-depth HGM step",
        n_valid_footprint=int(g.footprint.sum()),
        n_lidar_cells=int(lidar_valid.sum()),
        lidar_coverage_fraction_of_footprint=float((lidar_valid & g.footprint).sum() / g.footprint.sum()),
        n_basin_corridor_cells=int(working.sum()),
        n_lidar_scarp_ridge_centres=int(ridges.sum()),
        n_ribbon_positive_pixels=int((field > 0).sum()),
        max_score=float(field.max()),
        ribbon_width_px=3,
        corridor_px=H.CORRIDOR_PX,
        corridor_width_m=2 * H.CORRIDOR_PX * 100,
        depth_floor_m=H.BASIN_FLOOR_M,
        minimum_basement_throw_m=H.MIN_THROW_M,
        feature_stack="19 pinned competition bands plus public 12-band lidar descriptor raster",
        catalogue_used_in_feature_generation=False,
    )
    return field, features, meta


def _feature_canary(features, folds, valid, seed=6101):
    rng = np.random.default_rng(seed)
    pos_parts: dict[str, list[np.ndarray]] = {name: [] for name in features}
    neg_parts: dict[str, list[np.ndarray]] = {name: [] for name in features}
    for fold in folds:
        active = valid & np.asarray(fold["region"], bool) & ~np.asarray(fold["masked_known"], bool)
        truth = active & np.asarray(fold["truth"], bool)
        background = active & ~truth
        pi = np.flatnonzero(truth)
        ni = np.flatnonzero(background)
        if pi.size == 0 or ni.size == 0:
            continue
        nneg = min(20_000, ni.size)
        ni = rng.choice(ni, size=nneg, replace=False)
        for name, feature in features.items():
            pos_parts[name].append(np.asarray(feature, np.float32).ravel()[pi])
            neg_parts[name].append(np.asarray(feature, np.float32).ravel()[ni])
    out = {}
    for name in features:
        pos = np.concatenate(pos_parts[name]) if pos_parts[name] else np.zeros(0, np.float32)
        neg = np.concatenate(neg_parts[name]) if neg_parts[name] else np.zeros(0, np.float32)
        auc = H.auc_rank(pos, neg)
        out[name] = dict(auc=float(auc), n_pos=int(pos.size), n_neg=int(neg.size),
                         threshold=0.90, passed=bool(np.isfinite(auc) and auc <= 0.90))
    return dict(threshold=0.90, passed=bool(all(row["passed"] for row in out.values())),
                worst_auc=max((r["auc"] for r in out.values() if np.isfinite(r["auc"])), default=None),
                features=out)


def _evaluate_arms(predictions, folds, g):
    terms = {name: [] for name in predictions}
    fold_scores = {name: [] for name in predictions}
    withheld = 0
    for fold in folds:
        for name, pred in predictions.items():
            result, block_terms = evaluator.evaluate(
                pred, fold, g.footprint, block_side=200, origin=(0, 0), global_shape=g.shape)
            terms[name].append(block_terms)
            fold_scores[name].append(result)
        withheld += int(np.asarray(fold["truth"], bool)[np.asarray(fold["region"], bool)].sum())
    pooled_terms = {name: np.sum(np.stack(items, axis=0), axis=0)
                    for name, items in terms.items()}
    return pooled_terms, fold_scores, withheld


def _segment_recovery(pred, folds, seg, depth, valid):
    all_rows = []
    for fold in folds:
        region = np.asarray(fold["region"], bool)
        known = np.asarray(fold["masked_known"], bool)
        hidden = np.asarray(fold["truth"], bool) & region
        prediction = (np.asarray(pred) > 0.0) & valid & region & ~known
        distance = ndi.distance_transform_edt(~prediction)
        ids = np.unique(seg[hidden])
        ids = ids[ids > 0]
        for sid in ids:
            mask = (seg == sid) & hidden
            if not mask.any():
                continue
            all_rows.append(dict(
                fold=fold["name"], segment_id=int(sid), pixels=int(mask.sum()),
                median_depth_m=float(np.median(depth[mask])),
                recovered_300m=bool((distance[mask] <= 3.0).any()),
            ))
    basin = [row for row in all_rows if row["median_depth_m"] > 300.0]
    return dict(
        all=dict(withheld=len(all_rows), recovered=sum(r["recovered_300m"] for r in all_rows),
                 rate=(sum(r["recovered_300m"] for r in all_rows) / len(all_rows)) if all_rows else None),
        basin_interior_depth_gt_300m=dict(
            withheld=len(basin), recovered=sum(r["recovered_300m"] for r in basin),
            rate=(sum(r["recovered_300m"] for r in basin) / len(basin)) if basin else None,
            ci95=list(H.wilson(sum(r["recovered_300m"] for r in basin), len(basin))) if basin else None),
        rows=all_rows,
    )


def _holdout(field, features, meta, lidar_source, surface_report, g):
    folds, quad = holdoutmod.buffered_component_draw(
        g, seed=61, hide_frac=0.20, buffer_px=3, boundary_px=holdoutmod.DOMAIN_ERODE)
    candidate_name = "H61-L 3DEP scarp ribbons in basement-step corridors"
    positive_count = int((field > 0).sum())
    random_lines = H.random_lines(g.shape, g.footprint, positive_count, seed=6102)
    if int(random_lines.sum()) != positive_count:
        raise RuntimeError(f"shared random-line generator returned {int(random_lines.sum())}, expected {positive_count}")

    index = json.loads(INDEX.read_text())
    best_reference = next((r for r in index["rasters"]
                           if "gems19-h19-5-powerlaw-budget-multiline-corroborated" in r["file"]), None)
    if best_reference is None:
        raise RuntimeError("the declared inventory has no h19-5 comparator; cannot test against holdout best")
    with rasterio.open(best_reference["cache_file"]) as src:
        h19 = src.read(1).astype(np.float32)
    h19 = np.where(np.isfinite(h19), h19, 0.0)
    if h19.min() < 0 or h19.max() > 1:
        raise ValueError("registry holdout comparator is outside [0,1]")

    predictions = {
        candidate_name: field,
        "CONTROL random lines (matched positive-pixel count)": random_lines.astype(np.float32),
        "HOLDOUT-DTI reference raster h19-5 (as-published)": h19,
    }
    pooled_terms, fold_scores, withheld = _evaluate_arms(predictions, folds, g)
    summary = evaluator.pooled_summary(pooled_terms, draws=1000, seed=6103,
                                       candidate=candidate_name)

    # Whole catalogue segments are scored by proximity to each fold's prediction;
    # depth > 300 m is the declared basin-interior subset.
    seg, n_seg, _ = network.segments(g.catalogue, max_len_px=holdoutmod.MAX_SEG_PX)
    valid = g.footprint
    depth = np.load(CACHE / "depth_full.npy").astype(np.float32)
    recovery = {name: _segment_recovery(pred, folds, seg, depth, valid)
                for name, pred in predictions.items()}
    canary = _feature_canary(features, folds, valid)

    controls = [name for name in predictions if name != candidate_name]
    best_control = max(controls, key=lambda name: summary["scores"][name]["dti"])
    paired = summary["paired_differences"][best_control]
    beats_best = bool(paired["ci95"][0] > 0.0)
    result = dict(
        evidence_class="HOLDOUT-DTI",
        hypothesis=meta["candidate"],
        evaluator="gems61.evaluate_holdout v2; buffered whole-component quadrant hide-and-recover",
        evaluator_version=evaluator.VERSION,
        alpha=metric.ALPHA, beta=metric.BETA, triangular_radius_m=metric.R_M,
        n_withheld_positive_pixels=withheld,
        fold_receipts=[fold["receipt"] for fold in folds],
        pooled_summary=summary,
        best_comparable_control=best_control,
        candidate_beats_best_control_with_paired_95pct_ci=beats_best,
        basin_interior_segment_recovery_vs_random_lines=dict(
            candidate=recovery[candidate_name]["basin_interior_depth_gt_300m"],
            random_lines=recovery["CONTROL random lines (matched positive-pixel count)"]["basin_interior_depth_gt_300m"],
            reference_raster=recovery["HOLDOUT-DTI reference raster h19-5 (as-published)"]["basin_interior_depth_gt_300m"],
        ),
        segment_recovery=recovery,
        feature_alone_leakage_canary=canary,
        surface_uniqueness_verdict=surface_report["verdict"],
        lidar_source_sha256=lidar_source["local_sha256"],
        surface_metadata=meta,
        fold_score_detail={name: rows for name, rows in fold_scores.items()},
        promotion_eligibility=bool(beats_best and canary["passed"]),
        organizer_confirmed_score=None,
        caveat=("HOLDOUT-DTI estimates recovery of withheld mapped catalogue components, not organizer truth. "
                "The h19-5 row is a fixed reference raster scored by this evaluator; its reported live score, "
                "if any, is not used here and has no artifact-bound organizer receipt."),
    )
    write_json("h61l_holdout.json", result)
    return result, field


def _write_final(field, holdout_result, lidar_source, g):
    candidate_name = "H61-L 3DEP scarp ribbons in basement-step corridors"
    summary = holdout_result["pooled_summary"]
    score = summary["scores"][candidate_name]
    if not holdout_result["promotion_eligibility"]:
        write_json("h61l_final.json", dict(
            evidence_class="MEASURED / HOLDOUT-DTI",
            file_created=False,
            verdict="NEGATIVE — do not spend a weekly slot",
            reason="candidate did not beat the best comparable holdout control with a paired 95% CI above zero, "
                   "or the feature-alone leakage canary failed",
            holdout_dti=score,
            organizer_confirmed_score=None,
            downloadable_submission=None,
        ))
        return

    inventory = json.loads(INDEX.read_text())
    final = np.asarray(field, np.float32)
    final[~g.footprint] = 0.0
    final_gate = gates.lane_uniqueness_report(
        final, g.footprint, sample=gridmod.DATA_DIR / "sample_submission.tif",
        phase="dots", registry_index=inventory,
        log=lambda msg: print(msg, flush=True))
    write_json("h61l_final_dots_uniqueness.json", final_gate)
    if not final_gate["ok"]:
        write_json("h61l_final.json", dict(file_created=False,
            verdict="DUPLICATE — final-dot uniqueness stop", final_uniqueness=final_gate,
            organizer_confirmed_score=None))
        return

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = sha256_bytes(final.tobytes())
    npositive = int((final > 0).sum())
    name = f"gems61-h61l-3dep-scarp-step-ribbons-{npositive}px-{stamp}-{digest[:12]}"
    note = "H61-L: USGS 3DEP scarp ribbons inside GP-1012-calibrated basement-step corridors; HOLDOUT-DTI, live score pending"
    if len(note) > 140:
        raise AssertionError(f"submission note exceeds 140 characters: {len(note)}")
    OUT.mkdir(exist_ok=True)
    receipt = submission_writer.write_submission(
        OUT / f"{name}.tif", final,
        sample=gridmod.DATA_DIR / "sample_submission.tif", footprint=g.footprint,
        note=note, name=name,
        metadata=dict(hypothesis="H61-L", holdout_dti=score,
                     evaluator=holdout_result["evaluator"],
                     n_withheld_positive_pixels=holdout_result["n_withheld_positive_pixels"],
                     lidar_sha256=lidar_source["local_sha256"],
                     strict_surface_uniqueness=holdout_result["surface_uniqueness_verdict"],
                     final_dot_uniqueness=final_gate["verdict"],
                     approved_for_weekly_slot=False))
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    for suffix in (".tif", ".zip", ".json"):
        shutil.copy2(OUT / f"{name}{suffix}", DOWNLOADS / f"{name}{suffix}")
    write_json("h61l_final.json", dict(
        evidence_class="MEASURED + HOLDOUT-DTI",
        file_created=True, file=f"docs/downloads/{name}.tif", zip=f"docs/downloads/{name}.zip",
        receipt=f"docs/downloads/{name}.json", sha256=receipt["sha256"],
        bytes=receipt["bytes"], n_positive_pixels=npositive,
        holdout_dti=score, note=note, note_chars=len(note),
        validator=receipt["validator"], final_uniqueness=final_gate,
        verdict="UNSCORED-LIVE; weekly-slot decision remains with selector",
        organizer_confirmed_score=None,
    ))


def main() -> None:
    g = gridmod.load_grid()
    source = _record_lidar_provenance()
    field, features, meta = _build_surface(g)
    if not INDEX.is_file():
        raise SystemExit("missing evidence/registry_accessible_index.json; inventory is required and must fail closed")
    inventory = json.loads(INDEX.read_text())
    surface_gate = gates.lane_uniqueness_report(
        field, g.footprint, sample=gridmod.DATA_DIR / "sample_submission.tif",
        phase="surface", registry_index=inventory,
        log=lambda msg: print(msg, flush=True))
    payload = dict(
        evidence_class="MEASURED — pre-placement surface gate",
        hypothesis=meta["candidate"], method=meta["method"],
        source=source, surface_metadata=meta,
        surface_sha256=sha256_bytes(field.tobytes()),
        uniqueness=surface_gate,
        action=("STOP: duplicate/lane-drift or inventory failure; do not place, score, or write a TIFF"
                if not surface_gate["ok"] else "SURFACE CLEARED: proceed to shared spatial-blocked holdout"),
        holdout_status=("NOT RUN — strict pre-placement uniqueness stop" if not surface_gate["ok"] else "pending"),
        submission_slots_used=0,
    )
    write_json("h61l_surface.json", payload)
    print(f"H61-L pre-placement result: {surface_gate['verdict']}", flush=True)
    if not surface_gate["ok"]:
        print("STOP: per the literal protocol, do not run holdout or place dots for this duplicate surface.", flush=True)
        return

    holdout_result, field = _holdout(field, features, meta, source, surface_gate, g)
    _write_final(field, holdout_result, source, g)


if __name__ == "__main__":
    main()
