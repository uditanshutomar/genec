# GenEC Evaluation

## Primary Benchmark: 23 God Classes from 6 Open-Source Projects

The primary evaluation uses 23 large classes from well-known Apache Commons
libraries (IO, Lang, Collections, Text, Math) and JFreeChart.

Results in `results/live_evaluation/aggregate_results.json`:
- 23 classes evaluated end-to-end
- 506 total clusters detected, 76 post-filter suggestions
- **71/76 verified (93.4%)** — compilation + semantic + behavioral tests
- Average runtime: 57s per class

### Key contributions demonstrated

- **Safe, verified extractions**: 93.4% of suggestions pass compilation,
  semantic equivalence, and behavioral (test) verification via Maven builds.
- **Compilable code generation**: Every accepted suggestion produces code
  that compiles under the project's build system.
- **Test-preserving refactoring**: Behavioral verification ensures that
  existing test suites continue to pass after extraction.

Note: Traditional code-quality metrics (e.g., LCOM5) show only modest
change after extraction. The primary value is in producing *safe*,
developer-ready refactoring suggestions rather than maximising metric deltas.

## Baselines

Run with `scripts/run_baselines.py` on the same 23 classes:

1. **Field-sharing heuristic** (inspired by JDeodorant's agglomerative
   clustering approach): groups methods by shared field access using
   union-find. This is a simplified reimplementation, *not* the original
   JDeodorant Eclipse plugin.
2. **Random partitioning**: assigns methods to random clusters as a
   lower-bound sanity check.
3. **LLM-only** (no graph analysis): sends the class directly to an LLM
   without any structural or evolutionary analysis. Requires
   `ANTHROPIC_API_KEY`.

## Ablation Study

Configs in `configs/`: full, no_evolutionary, no_llm, no_verification, high_static

## Historical Results (MLCQ 50-class study)

Early development used a 50-class subset of the MLCQ dataset for rapid
iteration. Those results (e.g., 6/29 verified = 21%) were produced by a
*pre-fix version* of the codebase with weaker verification (syntactic-only)
and several bugs that have since been corrected. They are **not comparable**
to the current 23-class results and are retained only for historical
reference in `results/historical/`.

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
