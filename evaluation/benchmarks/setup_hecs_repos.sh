#!/usr/bin/env bash
# Setup HECS benchmark repositories for GenEC evaluation.
# Usage: ./setup_hecs_repos.sh
#
# Clones all 18 projects used in the HECS ECAccEval benchmark with FULL
# git history (required for evolutionary coupling mining and commit-SHA checkout).
# Repos are cloned to /tmp/hecs_repos/<project> to match run_hecs_benchmark.py.

set -euo pipefail

REPOS_DIR="/tmp/hecs_repos"
mkdir -p "$REPOS_DIR"

echo "=== HECS Benchmark Repository Setup ==="
echo "Target directory: $REPOS_DIR"
echo ""

# GitHub URLs for all 18 HECS benchmark projects.
# Full clones are required so that git checkout <commit_sha>^ works
# for the 21 instances with evolutionary context.
declare -A REPOS=(
    ["ZooNet"]="https://github.com/PaddlePaddle/PaddleClas.git"
    ["antlr4"]="https://github.com/antlr/antlr4.git"
    ["aws-sdk-java"]="https://github.com/aws/aws-sdk-java.git"
    ["buck"]="https://github.com/facebook/buck.git"
    ["cassandra"]="https://github.com/apache/cassandra.git"
    ["drill"]="https://github.com/apache/drill.git"
    ["eucalyptus"]="https://github.com/eucalyptus/eucalyptus.git"
    ["hazelcast"]="https://github.com/hazelcast/hazelcast.git"
    ["intellij-community"]="https://github.com/JetBrains/intellij-community.git"
    ["java-algorithms-implementation"]="https://github.com/phishman3579/java-algorithms-implementation.git"
    ["jetty"]="https://github.com/jetty/jetty.project.git"
    ["junit5"]="https://github.com/junit-team/junit5.git"
    ["languagetool"]="https://github.com/languagetool-org/languagetool.git"
    ["neo4j"]="https://github.com/neo4j/neo4j.git"
    ["robovm"]="https://github.com/MobiVM/robovm.git"
    ["spring-boot"]="https://github.com/spring-projects/spring-boot.git"
    ["wildfly"]="https://github.com/wildfly/wildfly.git"
    ["workflow-plugin"]="https://github.com/jenkinsci/workflow-plugin.git"
)

cloned=0
skipped=0
failed=0

for name in "${!REPOS[@]}"; do
    url="${REPOS[$name]}"
    target="$REPOS_DIR/$name"

    if [ -d "$target/.git" ]; then
        echo "[SKIP] $name already cloned at $target"
        ((skipped++))
    else
        echo "[CLONE] $name <- $url"
        if git clone "$url" "$target" 2>/dev/null; then
            ((cloned++))
        else
            echo "[FAIL] Could not clone $name from $url"
            ((failed++))
        fi
    fi
done

echo ""
echo "=== Setup complete ==="
echo "Cloned: $cloned | Skipped: $skipped | Failed: $failed"
echo ""
echo "NOTE: Full clones are used (not --depth=1) so that"
echo "run_hecs_benchmark.py can checkout historical commits"
echo "for the 21 instances with evolutionary context."

if [ "$failed" -gt 0 ]; then
    echo ""
    echo "WARNING: Some repos failed to clone. These instances will"
    echo "fall back to analyzing old.java from the HECS dataset."
    exit 1
fi
