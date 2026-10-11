#!/usr/bin/env bash
# Download every previously-SCORED submission raster that the GEMSDOE group published,
# so that the uniqueness check in this repository runs against the real registry and
# not against a description of it.
#
# WHY GIT AND NOT HTTP: raw.githubusercontent.com is not reachable from the sandbox
# this project is developed in; github.com is.  A blob-filtered clone with --no-checkout
# downloads no file contents at all, and `git show main:<path>` then fetches exactly
# one blob on demand.  That is the whole trick.
set -euo pipefail
DEST="$(mkdir -p "${1:-/tmp/refs/registry}" && cd "${1:-/tmp/refs/registry}" && pwd)"

# repo : path-within-repo   (the score the group reports for each file is in
#                            scripts/forensics_registry.py -> CLAIMED)
ITEMS="
GEMSDOE32:docs/downloads/gemsdoe32-h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros.tif
GEMSDOE32:docs/downloads/gems32-probe-S1-ANCHOR-identical-to-live-02600.tif
GEMSDOE28:docs/downloads/gems28-h36-1-rung30-blind-r1-20261003-b531dae0a36f-allfinite.tif
GEMSDOE28:docs/downloads/gems28-h27-4-r1-solo-d2-8-20261003-8acb75e1f2cc-allfinite.tif
GEMSDOE28:docs/downloads/gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-allfinite.tif
GEMSDOE25:docs/downloads/gems25-dotted-h19-5-d2-8-20261002-e56ea318af89-zeros.tif
GEMSDOE49:docs/downloads/gems49-gate_ortho_w0.25-40k-20261006T213721Z-zeros.tif
GEMSDOE29:docs/downloads/gemsdoe29-sgmc-off-catalogue-44k-20261003-c8dcd780e3fd-nan.tif
GEMSDOE30:docs/downloads/gemsdoe30-d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca.tif
"

echo "$ITEMS" | while IFS=: read -r repo path; do
  [ -z "$repo" ] && continue
  out="$DEST/$(basename "$path")"
  [ -f "$out" ] && { echo "have $(basename "$path")"; continue; }
  clone="/tmp/refs/.clone_$repo"
  if [ ! -d "$clone" ]; then
    echo "cloning $repo (blob-filtered)"
    git clone --quiet --filter=blob:none --no-checkout --depth 1 \
      "https://github.com/buffedlizard55-lab/$repo.git" "$clone"
  fi
  ( cd "$clone" && git show "main:$path" > "$out" )
  echo "fetched $(basename "$path")  $(wc -c < "$out") bytes"
done
echo "registry in $DEST"
