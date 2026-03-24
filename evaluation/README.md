# GenEC Evaluation

GenEC produces compilable, test-preserving Extract Class refactorings with
semantic names. This directory contains the benchmark, baseline comparisons,
ablation study, and user study protocol.

## Benchmark: 23 God Classes from 6 Open-Source Projects

The evaluation uses 23 large classes drawn from well-known Apache Commons
libraries (IO, Lang, Collections, Text, Math) and JFreeChart. Each class
was analyzed end-to-end by GenEC, with every suggestion verified through
compilation, semantic-equivalence checking, and behavioral (test-suite)
preservation via Maven builds.

### Benchmark Classes

| # | Project | Class | Methods | Fields |
|---|---------|-------|--------:|-------:|
| 1 | commons-io | IOUtils | 172 | 12 |
| 2 | commons-io | FileUtils | 159 | 18 |
| 3 | commons-io | FilenameUtils | 48 | 16 |
| 4 | commons-lang | StringUtils | 244 | 10 |
| 5 | commons-lang | ArrayUtils | 388 | 26 |
| 6 | commons-lang | NumberUtils | 68 | 21 |
| 7 | commons-lang | DateUtils | 67 | 12 |
| 8 | commons-lang | SystemUtils | 23 | 130 |
| 9 | commons-collections | CollectionUtils | 71 | 6 |
| 10 | commons-collections | MapUtils | 94 | 2 |
| 11 | commons-collections | IteratorUtils | 78 | 6 |
| 12 | jfreechart | XYPlot | 236 | 63 |
| 13 | jfreechart | CategoryPlot | 225 | 60 |
| 14 | jfreechart | PiePlot | 132 | 63 |
| 15 | jfreechart | AbstractRenderer | 169 | 59 |
| 16 | jfreechart | ChartPanel | 115 | 78 |
| 17 | commons-math | AccurateMath | 88 | 50 |
| 18 | commons-math | Dfp | 113 | 26 |
| 19 | commons-math | BOBYQAOptimizer | 13 | 37 |
| 20 | commons-math | DSCompiler | 48 | 8 |
| 21 | commons-text | TextStringBuilder | 169 | 12 |
| 22 | commons-text | StringLookupFactory | 41 | 28 |
| 23 | commons-text | StringSubstitutor | 62 | 16 |

### Results Summary

Results in `results/live_evaluation/aggregate_results.json`:
- 23 classes evaluated end-to-end
- 419 total clusters detected, 53 post-filter suggestions
- **41/53 verified (77.4%)** — compilation + semantic + behavioral tests
- Average runtime: 66s per class

### Key Contributions

- **Verification rate**: 77.4% of suggestions pass compilation, semantic
  equivalence, and behavioral verification via Maven builds.
- **Compilable code generation**: Every accepted suggestion produces code
  that compiles under the project's own build system.
- **Test-preserving refactoring**: Behavioral verification ensures that
  existing test suites continue to pass after extraction.
- **Semantic naming**: Extracted classes receive meaningful names (e.g.,
  `StreamCopier`, `DateTruncator`) rather than generic labels.

Note: Traditional code-quality metrics (e.g., LCOM5) show only modest
change after extraction. The primary value is in producing *safe*,
developer-ready refactoring suggestions rather than maximising metric deltas.

## Baselines

Run with `scripts/run_baselines.py` on the same 23 classes:

1. **Field-Sharing Heuristic**: Agglomerative clustering based on shared
   field access patterns, inspired by JDeodorant's Entity Placement
   algorithm but simplified. This is a structural-only reimplementation,
   *not* the original JDeodorant Eclipse plugin.
2. **Random Partitioning** (seed=42): Deterministic random grouping of
   methods. Lower bound showing that structure matters.
3. **LLM-Only** (no graph analysis): Sends the class directly to an LLM
   without any structural or evolutionary analysis. Requires
   `ANTHROPIC_API_KEY`.

For direct comparison with JDeodorant and HECS (ISSTA 2024), we cite their
published results on their respective datasets. Direct tool-to-tool
comparison on the same dataset is left as future work due to tool
availability constraints.

Comparison metrics: `scripts/compare_with_baselines.py`

## Ablation Study

Configs in `configs/`: full, no_evolutionary, no_llm, no_verification, high_static

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

### 4. Compare GenEC with baselines
```bash
python evaluation/scripts/compare_with_baselines.py
```

### 5. Compute statistics
```bash
# Without ground truth (compares GenEC vs field-sharing baseline):
python evaluation/scripts/compute_statistics.py \
  --results-dir evaluation/results/live_evaluation

# With ground truth (requires running RefactoringMiner first):
# java -jar RefactoringMiner.jar -a <repo> -json ground_truth.json
# python evaluation/scripts/compute_statistics.py \
#   --results-dir evaluation/results/live_evaluation \
#   --ground-truth-file <path-to-ground-truth.json>
```

### 6. Generate LaTeX tables
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
| RQ3 | Baseline comparison | `run_baselines.py`, `compare_with_baselines.py` |
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

---

### Appendix: Preliminary Results from Earlier Prototype

Early development used a 50-class subset of the MLCQ dataset for rapid
iteration. Those results (e.g., 6/29 verified = 21%) were produced by a
pre-fix version of the codebase with weaker verification (syntactic-only)
and several bugs that have since been corrected. They are **not comparable**
to the current 23-class results and are not used in any reported evaluation.
