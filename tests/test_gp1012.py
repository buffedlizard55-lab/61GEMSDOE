"""GP-1012 ingestion and fail-closed calibration policy."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems61 import basement_steps, buried, gp1012, grid, io, geo  # noqa: E402


def _header(rows=596, columns=504):
    return "\n".join([
        "file_title=GP-1012 Basin and Range depth grid",
        f"number_of_rows={rows}",
        f"number_of_columns={columns}",
        "grid_unit=kilometer",
        "grid_size(x)=2",
        "grid_size(y)=2",
        "grid_origin=lowerleft",
        "grid_sequence=left_right_up",
        "data_value_unit=kilometers",
        "missing_flag=9999",
        "xindex,yindex,depth",
    ]) + "\n"


def test_gp1012_parser_keeps_origin_missing_values_and_reports_measured_stats(tmp_path):
    path = tmp_path / "br_depth.xyz"
    path.write_text(_header() + "1,1,0.5\n504,596,9999\n", encoding="ascii")
    grid_ref = gp1012.read_gp1012_xyz(path, require_complete=False)
    assert grid_ref.depth_km.shape == (596, 504)
    assert grid_ref.depth_km[0, 0] == pytest.approx(0.5)
    assert np.isnan(grid_ref.depth_km[-1, -1])
    stats = grid_ref.summary()
    assert stats["evidence_class"] == "OFFICIAL-SOURCE-GRID-MEASUREMENT"
    assert stats["valid_cells"] == 1
    assert stats["p50_m"] == pytest.approx(500.0)
    assert len(stats["source_sha256"]) == 64
    assert "no geodetic datum" in stats["datum_warning"].lower()


def test_gp1012_parser_rejects_partial_download_as_calibration_reference(tmp_path):
    path = tmp_path / "partial.xyz"
    path.write_text(_header() + "1,1,0.5\n", encoding="ascii")
    with pytest.raises(ValueError, match="incomplete GP-1012 grid"):
        gp1012.read_gp1012_xyz(path)


def test_gp1012_parser_rejects_unexpected_units_and_duplicate_cells(tmp_path):
    units = tmp_path / "wrong-units.xyz"
    units.write_text(_header().replace("data_value_unit=kilometers", "data_value_unit=meters") +
                     "1,1,0.5\n", encoding="ascii")
    with pytest.raises(ValueError, match="data_value_unit"):
        gp1012.read_gp1012_xyz(units, require_complete=False)
    duplicate = tmp_path / "duplicate.xyz"
    duplicate.write_text(_header() + "1,1,0.5\n1,1,0.6\n", encoding="ascii")
    with pytest.raises(ValueError, match="duplicate GP-1012 cell"):
        gp1012.read_gp1012_xyz(duplicate, require_complete=False)


def test_band15_access_and_legacy_calibration_paths_fail_closed():
    with pytest.raises(PermissionError, match="band 15"):
        buried.load_band(15)
    with pytest.raises(PermissionError, match="band 15"):
        grid.load_band(15)
    names = [f"band-{i:02d}" for i in range(1, 20)]
    names[14] = "depth_to_base_surf"
    legacy_grid = io.Grid(height=1, width=1, footprint=np.ones((1, 1), bool),
                          catalogue=np.zeros((1, 1), bool),
                          bands=np.zeros((1, 1, 19), np.float32), names=names,
                          transform=(), crs="EPSG:32611")
    with pytest.raises(PermissionError, match="organizer band 15"):
        legacy_grid.band("depth_to_base_surf")
    assert "g_base_edge" not in geo.GEO_FEATURES
    assert 15 not in geo._BAND.values()
    gravity = np.zeros((8, 8), np.float32)
    valid = np.ones_like(gravity, bool)
    with pytest.raises(RuntimeError, match="GP-1012 calibration blocked"):
        buried.calibrate_density_scale(gravity, valid, candidates=(-400.0,),
                                       kc_scales=(1.0,), z0_candidates=(500.0,))
    with pytest.raises(RuntimeError, match="band 15 is prohibited"):
        buried.compare_to_published_depth(gravity, gravity, valid)
    with pytest.raises(RuntimeError, match="organizer band 15 is prohibited"):
        basement_steps.calibrate_z0(gravity, valid, gravity, [500.0], -400.0,
                                    8000.0, 2.0, 1.0)
