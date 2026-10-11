"""The competing explanation: a lateral density contrast *within* basement.

A step in the isostatic-gravity field has two candidate causes:

1. **Structure** -- the basement surface is vertically offset by a buried fault,
   so the thickness of the low-density basin fill changes across the step.  This
   is the target of the lane.
2. **Lithology** -- the basement keeps a constant depth but its density changes
   laterally across a lithologic contact (a granitic body against mafic
   volcanics, a hydrothermally altered zone, a low-density caldera fill or a
   thick palaeo-weathered horizon).  The gravity expression of a 200 kg/m^3
   intra-basement contrast over 2 km of section is indistinguishable from a
   ~100 m step of the basement surface at 400 kg/m^3, and it produces **no
   fault**.

The two are separated here with an *independent* physics: a lithologic contact
is a magnetic (and radiometric) contact, whereas a pure basement offset is not
necessarily one.  Where a gravity step coincides with a magnetic lineament of
the same strike, the structural interpretation is demoted.

This is a demotion, not a deletion: a fault that juxtaposes different
lithologies also produces both, so the test is conservative and its cost is
measured on the holdout rather than assumed.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt

from .steps import Steps, detect_steps


def magnetic_contact_crests(field: np.ndarray, sigma_grid=(1.0, 2.0, 4.0),
                            min_quantile: float = 0.90) -> np.ndarray:
    """Crest of the horizontal-gradient magnitude of a magnetic field.

    The same non-maximum-suppression operator as the basement steps, applied to
    ``rtp`` (reduced-to-pole magnetic intensity).  Kept above a high quantile so
    only genuine lithologic contacts, not textural magnetic noise, are flagged.
    """
    st: Steps = detect_steps(np.asarray(field, np.float32),
                             sigma_px=float(max(sigma_grid)), half_width_px=4.0)
    mag = st.gradient
    finite = np.isfinite(mag)
    if not finite.any():
        return np.zeros_like(st.crest)
    thr = float(np.quantile(mag[finite], min_quantile))
    return st.crest & (mag >= thr)


def coincidence_map(gravity_crest: np.ndarray, magnetic_crest: np.ndarray,
                    tolerance_px: float = 2.0) -> np.ndarray:
    """True where a gravity step crest lies within ``tolerance_px`` of a
    magnetic contact crest -- i.e. where the lithologic mimic is available."""
    magnetic_crest = np.asarray(magnetic_crest, bool)
    if not magnetic_crest.any():
        return np.zeros(np.asarray(gravity_crest).shape, bool)
    d = distance_transform_edt(~magnetic_crest)
    return np.asarray(gravity_crest, bool) & (d <= float(tolerance_px))


def density_contrast_equivalent_metres(drho_within_basement: float,
                                       section_thickness_m: float,
                                       drho_fill_basement: float) -> float:
    """Basement step (m) whose gravity signal equals an intra-basement contrast.

    ``drho_within_basement * section_thickness / drho_fill_basement``: for
    200 kg/m^3 over a 2 km section against a 400 kg/m^3 fill/basement contrast
    this is 1000 m -- an enormous apparent step from a contact that cuts no
    fault at all.  Reported in the run card so the ambiguity is quantitative.
    """
    return float(drho_within_basement) * float(section_thickness_m) / float(drho_fill_basement)
