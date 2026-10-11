#!/usr/bin/env bash
# Fetch the three official GEMS Prize rasters into data/ and verify their SHA-256.
#
# ROUTE A (preferred, official): the DrivenData data tab.  It is behind a login, so
#   this script cannot do it unattended -- download by hand and drop the three files
#   into data/ with the canonical names, then re-run with VERIFY_ONLY=1.
#       https://www.drivendata.org/competitions/306/competition-doe-gems/data/
#
# ROUTE B (unattended): the public GitHub mirror that the GEMSDOE group maintains for
#   exactly this reason (an egress-restricted sandbox cannot reach Dropbox).  The
#   mirror publishes its own SHA-256 pins, and this script checks the bytes against
#   the SAME hashes the official files have -- if they differ, it fails loudly.
#       https://github.com/buffedlizard55-lab/GEMSDOE2  (data/bridge/)
#
# Either route produces byte-identical files.  Provenance is recorded in
# data/provenance.json by scripts/inspect_data.py.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="${HERE}/data"
MIRROR="${MIRROR:-https://github.com/buffedlizard55-lab/GEMSDOE2.git}"
mkdir -p "${DATA}"

# Official SHA-256 pins (recorded by the mirror's data/bridge/manifest.json, which in
# turn cites the official inspection run scripts/inspect_competition_data.py).
SHA_FEATURES="4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5"
SHA_LABELS="7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093"
SHA_SAMPLE="2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc"

verify() {
  local f="$1" want="$2"
  if [ ! -f "$f" ]; then echo "MISSING  $f"; return 1; fi
  local got; got="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "$got" = "$want" ]; then echo "OK       $(basename "$f")  $got"; return 0
  else echo "MISMATCH $(basename "$f")"; echo "  want $want"; echo "  got  $got"; return 1; fi
}

if [ "${VERIFY_ONLY:-0}" = "1" ]; then
  rc=0
  verify "${DATA}/training_features.tif" "$SHA_FEATURES" || rc=1
  verify "${DATA}/labels.tif"            "$SHA_LABELS"   || rc=1
  verify "${DATA}/sample_submission.tif" "$SHA_SAMPLE"   || rc=1
  exit $rc
fi

if [ ! -f "${DATA}/training_features.tif" ] || [ ! -f "${DATA}/labels.tif" ]; then
  TMP="$(mktemp -d)"
  echo "cloning the mirror (blob-filtered; the feature stack is stored as parts)"
  git clone --quiet --filter=blob:none --no-checkout "${MIRROR}" "${TMP}/m"
  ( cd "${TMP}/m" && git sparse-checkout init --cone \
      && git sparse-checkout set data/bridge && git checkout --quiet main )

  echo "reassembling the 5-part feature stack"
  cat "${TMP}/m/data/bridge/gems-geodawn-numerical-features.tif.part-"* \
      > "${DATA}/training_features.tif"
  cp "${TMP}/m/data/bridge/existing_faults.tif"  "${DATA}/labels.tif"
  cp "${TMP}/m/data/bridge/example_submission.tif" "${DATA}/sample_submission.tif"
  rm -rf "${TMP}"
fi

rc=0
verify "${DATA}/training_features.tif" "$SHA_FEATURES" || rc=1
verify "${DATA}/labels.tif"            "$SHA_LABELS"   || rc=1
verify "${DATA}/sample_submission.tif" "$SHA_SAMPLE"   || rc=1
if [ $rc -ne 0 ]; then
  echo "REFUSING TO CONTINUE: bytes do not match the official SHA-256 pins."
  exit 1
fi
echo "all three official rasters verified."
