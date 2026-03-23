# GenEC Evaluation

## Primary Benchmark: 23 God Classes from 6 Open-Source Projects

Results in `results/live_evaluation/aggregate_results.json`:
- 23 classes from Apache Commons (IO, Lang, Collections, Text, Math) and JFreeChart
- 506 total clusters detected, 76 post-filter suggestions
- **71/76 verified (93.4%)** — compilation + semantic + behavioral tests
- Average runtime: 57s per class

## Baselines

Run with `scripts/run_baselines.py` on the same 23 classes:
- **Field-sharing heuristic** (inspired by JDeodorant's approach): 37 suggestions
- **Random partition**: 462 suggestions
- **LLM-only** (no graph analysis): run via `LLMOnlyBaseline` (requires `ANTHROPIC_API_KEY`)

Note: The field-sharing baseline is a reimplementation of JDeodorant's core
agglomerative clustering algorithm, not the original Eclipse plugin.

## Ablation Study

Configs in `configs/`: full, no_evolutionary, no_llm, no_verification, high_static

## Historical Results

Pre-optimization results from earlier development are in `results/historical/`.
These used weaker verification (syntactic-only) and are not comparable to the
current results.

## User Study

Protocol in `user_study/study_protocol.md`. Participant results pending.

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

### 2. Run full evaluation
```bash
python evaluation/scripts/run_live_evaluation.py
```

### 3. Run baselines
```bash
python evaluation/scripts/run_baselines.py
```

### 4. Compute statistics
```bash
python evaluation/scripts/compute_statistics.py \
  --results-dir evaluation/results/live_evaluation \
  --ground-truth-file evaluation/ground_truth/refactoring_miner_results.json
```

### 5. Generate LaTeX tables
```bash
python evaluation/scripts/generate_latex_tables.py \
  --results-dir evaluation/results/live_evaluation \
  --output-dir evaluation/results/tables
```

## Research Questions

| RQ | Question | Script |
|----|----------|--------|
| RQ1 | Verification rate and extraction quality | `run_live_evaluation.py` |
| RQ2 | Component contributions (ablation) | `run_ablation.py` |
| RQ3 | Baseline comparison | `run_baselines.py` |
| RQ4 | Developer perception | `user_study/analyze_results.py` |

## Configuration

- **LLM Model**: Claude Sonnet 4 (`claude-sonnet-4-20250514`)
- **Temperature**: 0.2 (for naming consistency)
- **Graph fusion**: alpha=0.6 (60% static, 40% evolutionary)
- **Clustering**: Leiden algorithm, resolution=0.5, min_size=3

## API Costs

Approximate costs per full evaluation run:
- Full evaluation (23 classes): ~$8-12 in Claude API calls
- Ablation (15 classes x 5 variants): ~$20-30
- LLM-only baseline (23 classes): ~$5-10
