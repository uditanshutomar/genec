# GenEC Evaluation & Reproducibility Package

This directory contains the complete evaluation infrastructure for the GenEC paper:
"GenEC: A Hybrid Framework for Safe and Explainable Extract Class Refactoring"

## Directory Structure

```
evaluation/
  benchmarks/          # Benchmark class specifications
  baselines/           # Baseline implementations (LLM-only, JDeodorant, Random)
  configs/             # Ablation study configuration variants
  ground_truth/        # RefactoringMiner ground truth data
  results/             # Generated results (JSON + LaTeX tables)
  scripts/             # Evaluation and analysis scripts
  user_study/          # Developer study materials
```

## Prerequisites

- Python 3.10+
- Java 11+ (for JDT wrapper and RefactoringMiner)
- Anthropic API key (set `ANTHROPIC_API_KEY` environment variable)
- GenEC installed: `pip install -e .`
- JDT wrapper built: `cd genec-jdt-wrapper && mvn package`

## Quick Start

### 1. Set up benchmarks
```bash
# Clone benchmark repositories at pinned commits
./evaluation/benchmarks/setup_benchmarks.sh
```

### 2. Run full evaluation (RQ1)
```bash
python evaluation/scripts/run_full_evaluation.py \
  --benchmark-file evaluation/benchmarks/benchmark_classes.json \
  --output-dir evaluation/results
```

### 3. Run ablation study (RQ2)
```bash
python evaluation/scripts/run_ablation.py \
  --benchmark-file evaluation/benchmarks/benchmark_classes.json \
  --output-dir evaluation/results \
  --max-classes 15
```

### 4. Compute statistics
```bash
python evaluation/scripts/compute_statistics.py \
  --results-dir evaluation/results \
  --ground-truth-file evaluation/ground_truth/refactoring_miner_results.json
```

### 5. Generate LaTeX tables
```bash
python evaluation/scripts/generate_latex_tables.py \
  --results-dir evaluation/results \
  --output-dir evaluation/results/tables
```

## Research Questions

| RQ | Question | Script |
|----|----------|--------|
| RQ1 | Semantic coherence vs baselines | `run_full_evaluation.py` |
| RQ2 | Component contributions (ablation) | `run_ablation.py` |
| RQ3 | Verification effectiveness | `run_full_evaluation.py` (verification stats) |
| RQ4 | Developer perception | `user_study/analyze_results.py` |

## Configuration

- **LLM Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Temperature**: 0.2 (for naming consistency)
- **Graph fusion**: alpha=0.6 (60% static, 40% evolutionary)
- **Clustering**: Leiden algorithm, resolution=0.5, min_size=3
- **Benchmark**: MLCQ dataset (50 God Classes from 12 Apache projects)

## API Costs

Approximate costs per full evaluation run:
- Full evaluation (50 classes): ~$15-25 in Claude API calls
- Ablation (15 classes x 5 variants): ~$20-30
- LLM-only baseline (50 classes): ~$10-15
