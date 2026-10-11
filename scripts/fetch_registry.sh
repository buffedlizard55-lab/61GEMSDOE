#!/usr/bin/env bash
# Fetch the explicit public owner-repository raster inventory used by the local
# uniqueness gate. This is a reproducible *declared scope*, not an organizer-side
# complete registry; see evidence/registry_accessible_index.json.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="$(mkdir -p "${1:-/tmp/refs/registry}" && cd "${1:-/tmp/refs/registry}" && pwd)"

while IFS=$'\t' read -r repo path; do
  [ -z "${repo:-}" ] && continue
  case "$repo" in \#*) continue;; esac
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
done < "$SCRIPT_DIR/registry_sources.tsv"

echo "public raster cache in $DEST"
echo "Build the auditable index with: PYTHONPATH=src .venv/bin/python scripts/build_registry_index.py --public-cache '$DEST'"
