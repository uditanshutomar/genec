#!/usr/bin/env bash
# Setup benchmark repositories at pinned commits for GenEC evaluation.
# Usage: ./setup_benchmarks.sh
#
# Clones each benchmark project and checks out the specific commit
# used in the evaluation to ensure reproducibility.
# Repositories are cloned to /tmp/<project> to match benchmark_classes.json paths.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCHMARK_FILE="$SCRIPT_DIR/benchmark_classes.json"

echo "=== GenEC Benchmark Setup ==="
echo ""

# Extract repositories from the JSON and clone them
python3 -c "
import json, sys
with open('$BENCHMARK_FILE') as f:
    data = json.load(f)

for name, repo in data.get('repositories', {}).items():
    url = repo['repo_url']
    path = repo['clone_path']
    commit = repo.get('commit_sha', 'HEAD')
    print(f'{name}|{url}|{path}|{commit}')
" | while IFS='|' read -r name repo_url clone_path commit_sha; do
    if [ -d "$clone_path/.git" ]; then
        echo "[SKIP] $clone_path already exists"
    else
        echo "[CLONE] $repo_url -> $clone_path (full history for evolutionary coupling)"
        git clone "$repo_url" "$clone_path"

        if [ "$commit_sha" != "HEAD" ]; then
            echo "[CHECKOUT] $commit_sha"
            cd "$clone_path"
            git checkout "$commit_sha" 2>/dev/null || echo "[WARN] Could not checkout $commit_sha"
            cd - >/dev/null
        fi
    fi
done

echo ""
echo "=== Setup complete ==="
echo "Benchmark repositories cloned to /tmp/<project>"
echo ""

# Verify all class files exist
echo "Verifying benchmark class files..."
python3 -c "
import json, os
with open('$BENCHMARK_FILE') as f:
    data = json.load(f)
for cls in data['classes']:
    full_path = os.path.join(cls['repo_path'], cls['class_file'])
    status = 'OK' if os.path.exists(full_path) else 'MISSING'
    print(f'  [{status}] {cls[\"class_name\"]} ({full_path})')
"
