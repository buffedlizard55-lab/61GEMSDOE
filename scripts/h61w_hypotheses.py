#!/usr/bin/env python3
"""Write evidence/h61w_hypotheses.json -- the ranked candidate list for 61GEMSDOE.

Rank 1 is the hypothesis this session built and measured on the shared holdout
instrument.  Ranks 2-6 are not yet implemented; each names its layers, its
physical signature, why it should catch a fault the catalogue misses rather than
one it already contains, how it differs from everything already in this
repository, its expected gain, its implementation cost, and its data
obtainability (verified or not).

Run:  PYTHONPATH=src python3 scripts/h61w_hypotheses.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

H = [
    {
        "id": "H61-W",
        "rank": 1,
        "name": "Dip-projected basement-step trace, with an independent lidar scarp conjunction",
        "layers": ("Band 13 of the supplied stack (isostatic gravity anomaly) through the "
                   "Parker/Oldenburg inversion -> depth to basement; the auxiliary lidar scarp "
                   "feature raster (topographic-scarp detector) as the competing-explanation "
                   "test; band 19 (detrended-elevation slope) only in the control arm."),
        "signature": ("Directional geometry: the horizontal-gradient maximum of the inverted "
                      "basement depth sits z_b*cot(dip) basinward of the surface fault trace. "
                      "Projecting the step toward its footwall by that distance is a "
                      "depth-dependent, sign-definite correction, not a symmetric dilation. The "
                      "conjunction with a surface scarp rejects the intrabasement contact."),
        "why_missing": ("Alluvial cover is why the catalogue misses these faults, and it is also "
                        "why the two classical signals separate: gravity keeps the basement step, "
                        "surface mapping keeps only the scarp. A projection turns the first into "
                        "the second's position; the conjunction keeps only the steps that have "
                        "both, so it cannot merely re-find a fault that is already in the "
                        "catalogue because such a fault has no un-mapped scarp to add."),
        "differs_from": ("No session in this repository applied a dip projection, and none used "
                         "the inverted depth value to place a dot rather than only to gate a "
                         "corridor. The 100 m-aggregated lidar scarp raster had never been read "
                         "by this lane at all."),
        "gain": "Low (PROJECTION ONLY, before measurement).",
        "cost": "Medium -- implemented and measured this session.",
        "measured": ("HOLDOUT-DTI 0.0149 (95 % CI 0.0122-0.0173) against 0.0227 for random dotted "
                     "lines, 0.0093 for its own unprojected ablation (so the projection is worth "
                     "+60 % on the step field) and 0.0267 for the previous session's corridor x "
                     "slope-ridge arm. NEGATIVE: the projection improves its base but the base "
                     "itself scores below random lines. Label-aware screen: the projected trace "
                     "x scarp conjunction is within 300 m of a mapped trace 13.7 % of the time "
                     "against 8.7 % for a random pixel (1.57x)."),
        "obtainable": "Yes -- every input is either supplied by the organisers or fetched from a "
                      "public GitHub mirror this session (sha256 recorded in "
                      "evidence/h61w_aux.json).",
    },
    {
        "id": "H61-3DEP",
        "rank": 2,
        "name": "Metre-scale 3DEP scarp detection at native resolution inside the basement-step corridor",
        "layers": ("USGS 3DEP lidar DEM at 1 m (or the group's 3 m derivative mirror) plus this "
                   "lane's 200 m Parker/Oldenburg basement-step corridor and basin mask as the "
                   "prior. The 100 m-aggregated scarp raster this session used is only the "
                   "aggregate of the same source."),
        "signature": ("A slope break plus a curvature couplet along strike: scarp height 0.5-5 m, "
                      "crest-to-toe curvature pair, local-relief model. This is the primary "
                      "evidence a field mapper uses; at 100 m it is averaged away."),
        "why_missing": ("The supplied 100 m grid cannot represent a 1 m scarp, and the catalogue "
                        "was compiled from 1:24k-1:250k mapping in which a 1 m scarp in young "
                        "alluvium is below the resolution of the publication scale. The gravity "
                        "corridor is what stops this being a generic scarp hunt: without it the "
                        "detector fires on fan toes, terrace risers and incised channels, which "
                        "is exactly why the group's standalone lidar files plateau at 0.13-0.15."),
        "differs_from": ("The group's lidar files (7GEMSDOE 0.1461, 12GEMSDOE 0.1294 live) ran "
                         "with no gravity prior and no basin gate. This lane has never read a "
                         "DEM. The measurement this session is the quantitative reason to try: "
                         "the 100 m aggregation of the same source is enriched only 1.10x over "
                         "random within 300 m of a mapped trace, so the untested part is the "
                         "resolution, not the source."),
        "gain": "Highest of the untried set, because it is the only proposal that adds "
                "information the 100 m grid does not contain. PROJECTION ONLY.",
        "cost": ("High -- each 1 m tile is ~250-285 MB and the region needs many; the corpus "
                 "must be mirrored and pinned by sha256 exactly as the feature stack is."),
        "measured": "Not measured this session.",
        "obtainable": ("VERIFIED THIS SESSION. Official source: USGS 3DEP project "
                       "NV_WestCentral_EarthMRI_2020_D20, "
                       "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/1m/Projects/"
                       "NV_WestCentral_EarthMRI_2020_D20/TIFF/USGS_1M_11_<tile>_"
                       "NV_WestCentral_EarthMRI_2020_D20.tif , with source sha256 recorded in "
                       "GEMSDOE48 data/pilot/dem3m/dem_pilot_receipt.json (fetched and read this "
                       "session). Two 3 m re-sampled pilot tiles exist in that public mirror and "
                       "were downloaded and opened this session (3337 x 3337, 3.0 m, "
                       "EPSG:26911, int16 decimetres, no data gaps). The 1 m tiles themselves "
                       "are NOT reachable from this sandbox (egress allow-list, IR-61-NET-01), so "
                       "the route is: fetch on an unrestricted machine, mirror to GitHub, pin."),
    },
    {
        "id": "H61-DISCORD",
        "rank": 3,
        "name": "Depth-to-basement discordance: the organiser's compiled depth surface minus this lane's gravity inversion",
        "layers": ("Band 15 (depth to basement surface, the organisers' own compiled basin-depth "
                   "layer) and the Parker/Oldenburg inverted depth from band 13. Contrast with "
                   "the lane's GP-1012 calibration, which uses the published depth *scale* only."),
        "signature": ("A spatially coherent residual of one sign sustained over >= 3 km between "
                      "two independent estimates of the same surface. Where a gravity model and "
                      "a control-point compilation disagree by hundreds of metres over "
                      "kilometres, one of them is missing a structure."),
        "why_missing": ("A regional compilation is interpolated between sparse control; it "
                        "smooths through small basins, relay ramps and step-overs, so a real "
                        "fault-bounded sub-basin can be absent from it. The discordance is "
                        "therefore largest exactly where a compiled map is least able to "
                        "represent the truth, which is where unmapped faults live -- and, unlike "
                        "every topographic or magnetic field, it cannot re-express the already "
                        "mapped traces because both inputs are depth surfaces, not linework."),
        "differs_from": ("Previous sessions used band 15 only as a *correlation check* on their "
                         "inversion (r = 0.745 in the H61-MH session, and the first-experiment "
                         "receipt records a Pearson of -0.1822 for an uncalibrated variant). "
                         "Nobody has emitted on the residual itself, in either sign."),
        "gain": "Moderate. Cheap, uses only supplied layers, and targets the compiler's smoothing "
                "error rather than a geophysical field.",
        "cost": "Low -- both layers are already cached; one holdout pass.",
        "measured": "Not measured this session.",
        "obtainable": "Yes -- no external data at all.",
    },
    {
        "id": "H61-RELAY",
        "rank": 4,
        "name": "Relay and step-over closure on the basement-step network itself",
        "layers": ("This lane's inverted depth (band 13) only: the Blakely-Simpson maxima of "
                   "|grad depth|, formed into a network by gems61.network.segments, then paired "
                   "tip-to-tip."),
        "signature": ("Two step-segment tips 8-30 px apart with matched throw across the gap, "
                      "opposed footwall polarity and parallel-to-oblique strike. That is the "
                      "geometry of a relay ramp or a step-over, and the connecting strand is a "
                      "predictable, geometric object rather than a detected one."),
        "why_missing": ("A compiler will not add a strand across a relay without field evidence "
                        "that it exists, so the connection is systematically absent from the "
                        "catalogue while remaining the most probable place for a new strand. "
                        "Independent support: the family's highest live scores are the tip and "
                        "step-over constructions (h33d-analog-tip-stepover-r30 0.2632, "
                        "h36-1-rung30-blind-r1 0.2710), which is evidence that the hidden truth "
                        "is enriched at fault tips and relays."),
        "differs_from": ("Previous lane sessions used smoothing-scale persistence and corridors "
                         "-- both are per-pixel filters. Nobody used the *pairing geometry of "
                         "the step network*, and nobody in this lane has ever had a reason to: "
                         "the corridor is defined by a single step line, not by two."),
        "gain": "Moderate to high, and the cheapest of the high-value ideas: it needs no new data "
                "and it is the only proposal here whose geometry is corroborated by the live "
                "scores of the family's own files.",
        "cost": "Low-medium -- skeleton/segment analysis on a 100 m boolean mask; "
                "gems61.network already provides segments() and local_strike().",
        "measured": "Not measured this session.",
        "obtainable": "Yes -- no external data at all.",
    },
    {
        "id": "H61-SEIS-DEEP",
        "rank": 5,
        "name": "Basin-interior seismicity nucleation on a basement step",
        "layers": ("Bands 10 and 16 (distance to earthquake; earthquake intensity/density, both "
                   "with the n=100 km, a=15 deg parameterisation) conditioned on this lane's "
                   "basin mask (inverted depth > 300 m) and the projected step trace."),
        "signature": ("Anomalous event density at depth under a smooth basin, co-located with a "
                      "basement step. Microseismicity nucleates on critically stressed faults "
                      "whose frictional strength is low, which is the closest available proxy for "
                      "'a fault is slipping here now'."),
        "why_missing": ("A buried, currently active fault covered by kilometres of fill has no "
                        "surface expression to map, so it can only be found from depth. The "
                        "conditioning on the step is what makes it a fault detector rather than a "
                        "hazard map: an isolated cluster with no basement step is more likely a "
                        "network artefact or a volcanic/geothermal source."),
        "differs_from": ("The parked H61-R proposed the seismicity bands as a *global* locator. "
                         "No session has conditioned them on a basement step, and the lane's "
                         "competing explanation -- an intrabasement density contrast -- is "
                         "seismically silent, so the conjunction is also the discriminating test."),
        "gain": "Moderate. Band 16 carries the second-largest weight of all 28 channels in the "
                "previous session's logistic model (+0.890).",
        "cost": "Low -- both bands cached; one holdout pass.",
        "measured": "Not measured this session.",
        "obtainable": "Yes -- supplied layers only.",
    },
    {
        "id": "H61-GEOD-STEP",
        "rank": 6,
        "name": "Geodetic strain rate gated on the basement step",
        "layers": ("Bands 4, 7 and 8 (geodetic second invariant, shear rate, dilatation rate) "
                   "restricted to the 3 px dilation of the dip-projected step trace and to the "
                   "basin interior, thresholded at the band's own 90th percentile."),
        "signature": ("A present-day strain-rate maximum that is co-located with a basement step. "
                      "The step supplies the structural location; the strain field supplies the "
                      "evidence that the structure is active, which is the property a fault "
                      "needs to be worth mapping and the property a lithological contact never "
                      "has."),
        "why_missing": ("An active fault that is accumulating slip but has not yet produced a "
                        "mappable scarp shows up in geodesy through the regolith. Conditioning "
                        "on the gravity step removes the geodetic artefacts (monument noise, "
                        "long-wavelength interseismic loading) that dominate the raw bands."),
        "differs_from": ("The parked H61-Q proposed the geodetic bands as a global locator. The "
                         "previous session's logistic weights are the evidence that the layer "
                         "carries signal (band 07 +0.889, band 04 -0.628, so the naive "
                         "'high strain = fault' reading is wrong in sign for one of them), and no "
                         "session has used them as a conditional gate on the lane's own "
                         "structure."),
        "gain": "Low to moderate. PROJECTION ONLY.",
        "cost": "Low -- all inputs cached; one holdout pass.",
        "measured": "Not measured this session.",
        "obtainable": "Yes -- supplied layers only.",
    },
]

NOTE = (
    "Rank 1 is the hypothesis this session implemented and measured on the shared holdout "
    "instrument (gems61.holdout_segmented v2, seeds 20+21, mode all, 22,641 withheld truth px, "
    "alpha 0.2 / beta 0.8 / 300 m). Ranks 2-6 are proposals: none has been implemented, and "
    "every one of them is scored as a PROJECTION, never as a score. Ranks 5 and 6 restate two "
    "of the four hypotheses parked by the previous session (H61-R, H61-Q) with the conditioning "
    "that the previous session could not test because the corridor was not yet the artefact; "
    "they are kept because the layer weights are the measured reason to keep them."
)


def main() -> int:
    p = ROOT / "evidence" / "h61w_hypotheses.json"
    p.write_text(json.dumps(H, indent=2) + "\n")
    q = ROOT / "evidence" / "h61w_hypotheses_note.json"
    q.write_text(json.dumps({"note": NOTE}, indent=2) + "\n")
    print(f"wrote {p.relative_to(ROOT)} ({len(H)} hypotheses)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
