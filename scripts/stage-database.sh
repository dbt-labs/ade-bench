#!/bin/bash
# Upload one or more .duckdb files to a per-PR staging release.
#
# Usage: scripts/stage-database.sh shared/databases/duckdb/helixops_saas.duckdb
#
# Requires an open PR on the current branch. Run from the repo root.
set -euo pipefail

if [ $# -eq 0 ]; then
  echo "Usage: $0 <file.duckdb> [file2.duckdb ...]" >&2
  exit 1
fi

PR=$(gh pr view --json number --jq .number 2>/dev/null || true)
if [ -z "$PR" ]; then
  echo "Error: no open PR found for the current branch." >&2
  echo "Push your branch and open a PR first." >&2
  exit 1
fi

TAG="databases-staging-pr-${PR}"

if ! gh release view "$TAG" &>/dev/null; then
  gh release create "$TAG" \
    --prerelease \
    --title "Databases (staging PR #${PR})" \
    --notes "Staging DuckDB database files for PR #${PR}. Promoted to production on merge (see \`scripts/stage-database.sh\`)."
  echo "Created staging release $TAG"
fi

for file in "$@"; do
  echo "Uploading $(basename "$file") to $TAG..."
  gh release upload "$TAG" "$file" --clobber
done

echo ""
echo "Done. CI on PR #${PR} will use these staged files."
