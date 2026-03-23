#!/usr/bin/env bash
# Setup benchmark repositories at pinned commits for GenEC evaluation.
# Usage: ./setup_benchmarks.sh [--output-dir DIR]
#
# Clones each benchmark project and checks out the specific commit
# used in the evaluation to ensure reproducibility.

set -euo pipefail

OUTPUT_DIR="${1:-benchmarks/repos}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCHMARK_FILE="$SCRIPT_DIR/benchmark_classes.json"

echo "=== GenEC Benchmark Setup ==="
echo "Output directory: $OUTPUT_DIR"
echo ""

mkdir -p "$OUTPUT_DIR"

# Extract unique repositories from benchmark file
# Uses python to parse JSON (available since we require Python 3.10+)
python3 -c "
import json, sys
with open('$BENCHMARK_FILE') as f:
    data = json.load(f)

seen = set()
for cls in data['classes']:
    repo_url = cls['repo_url']
    repo_path = cls['repo_path']
    commit = cls.get('commit_sha', 'HEAD')
    key = repo_url
    if key not in seen:
        seen.add(key)
        print(f'{repo_url}|{repo_path}|{commit}')
" | while IFS='|' read -r repo_url repo_path commit_sha; do
    full_path="$OUTPUT_DIR/$(basename "$repo_path")"

    if [ -d "$full_path/.git" ]; then
        echo "[SKIP] $full_path already exists"
    else
        echo "[CLONE] $repo_url -> $full_path"
        git clone --depth=1 "$repo_url" "$full_path" 2>/dev/null || \
            git clone "$repo_url" "$full_path"

        if [ "$commit_sha" != "TO_BE_FILLED" ] && [ "$commit_sha" != "HEAD" ]; then
            echo "[CHECKOUT] $commit_sha"
            cd "$full_path"
            git fetch --depth=1 origin "$commit_sha" 2>/dev/null || true
            git checkout "$commit_sha" 2>/dev/null || echo "[WARN] Could not checkout $commit_sha"
            cd - >/dev/null
        fi
    fi
done

echo ""
echo "=== Setup complete ==="
echo "Benchmark repositories are in: $OUTPUT_DIR"
