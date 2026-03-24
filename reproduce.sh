#!/bin/bash
# One-command reproduction of GenEC evaluation results
# Usage: ./reproduce.sh [--with-llm]
#
# Prerequisites:
#   - Docker OR (Python 3.10+, Java 17+, Maven)
#   - For LLM features: ANTHROPIC_API_KEY environment variable
#
# This script:
# 1. Installs dependencies
# 2. Builds JDT wrapper
# 3. Runs the 23-class live evaluation
# 4. Runs baselines
# 5. Computes statistics
# 6. Generates LaTeX tables
set -e

echo "=== GenEC Evaluation Reproduction ==="
echo ""

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
command -v java >/dev/null 2>&1 || { echo "Java 17+ required"; exit 1; }
command -v mvn >/dev/null 2>&1 || { echo "Maven required"; exit 1; }

# Install
pip install -e . -q

# Build JDT
echo "Building JDT wrapper..."
cd genec-jdt-wrapper && mvn clean package -q -DskipTests && cd ..

# Run tests
echo "Running tests..."
python -m pytest tests/ -c /dev/null -q --ignore=tests/integration

# Clone benchmark repos
echo "Cloning benchmark repositories..."
bash evaluation/benchmarks/setup_benchmarks.sh

# Run evaluation
echo "Running live evaluation..."
python evaluation/scripts/run_live_evaluation.py

# Run baselines
echo "Running baselines..."
python evaluation/scripts/run_baselines.py

# Compute statistics
echo "Computing statistics..."
python evaluation/scripts/compute_statistics.py --results-dir evaluation/results/live_evaluation

# Generate tables
echo "Generating LaTeX tables..."
python evaluation/scripts/generate_latex_tables.py --results-dir evaluation/results/live_evaluation

echo ""
echo "=== Reproduction complete ==="
echo "Results in: evaluation/results/"
