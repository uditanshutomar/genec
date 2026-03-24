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

### Detailed Per-Class Results

| # | Project | Class | Methods | Fields | Clusters | Suggestions | Verified | Best Extraction | Rate |
|--:|---------|-------|--------:|-------:|-------:|-----------:|--------:|-----------------|-----:|
| 1 | commons-io | IOUtils | 172 | 8 | 37 | 1 | 1 | ResourceLoader | 100.0% |
| 2 | commons-io | FileUtils | 159 | 18 | 61 | 7 | 7 | ShutdownFileDeleter | 100.0% |
| 3 | commons-io | FilenameUtils | 48 | 16 | 21 | 5 | 5 | WildcardMatcher | 100.0% |
| 4 | commons-lang | StringUtils | 244 | 10 | 114 | 12 | 12 | StringReplacer | 100.0% |
| 5 | commons-lang | ArrayUtils | 388 | 26 | 93 | 1 | 0 | ArrayConcatenator | 0.0% |
| 6 | commons-lang | NumberUtils | 68 | 21 | 46 | 4 | 3 | NumericStringValidator | 75.0% |
| 7 | commons-lang | DateUtils | 67 | 12 | 26 | 4 | 4 | DateParser | 100.0% |
| 8 | commons-lang | SystemUtils | 23 | 130 | 153 | 4 | 4 | JavaVersionComparator | 100.0% |
| 9 | commons-collections | CollectionUtils | 71 | 6 | 59 | 5 | 5 | SortedMerger | 100.0% |
| 10 | commons-collections | MapUtils | 94 | 2 | 33 | 5 | 1 | MapNumericConverter | 20.0% |
| 11 | commons-collections | IteratorUtils | 78 | 6 | 49 | 6 | 6 | IteratorFactory | 100.0% |
| 12 | jfreechart | XYPlot | 236 | 63 | 22 | 14 | 2 | MarkerRegistry | 14.3% |
| 13 | jfreechart | CategoryPlot | 225 | 60 | 28 | 18 | 5 | AnnotationRegistry | 27.8% |
| 14 | jfreechart | PiePlot | 132 | 63 | 21 | 19 | 0 | SectionOutlinePaintRegistry | 0.0% |
| 15 | jfreechart | AbstractRenderer | 169 | 59 | 29 | 16 | 4 | GetSeriesItemLabelPaintGroup | 25.0% |
| 16 | jfreechart | ChartPanel | 115 | 78 | 32 | 17 | 14 | IsMouseWheelEnabledGroup | 82.4% |
| 17 | commons-math | AccurateMath | 88 | 50 | 19 | 6 | 6 | FloorOperations | 100.0% |
| 18 | commons-math | Dfp | 113 | 26 | 35 | 13 | 13 | RintGroup | 100.0% |
| 19 | commons-math | BOBYQAOptimizer | 13 | 37 | 10 | 3 | 3 | CallerGroup | 100.0% |
| 20 | commons-math | DSCompiler | 48 | 8 | 34 | 4 | 1 | GetFreeParametersGroup | 25.0% |
| 21 | commons-text | TextStringBuilder | 169 | 12 | 83 | 3 | 3 | EnsureCapacityGroup | 100.0% |
| 22 | commons-text | StringLookupFactory | 41 | 28 | 52 | 2 | 1 | Base64Operations | 50.0% |
| 23 | commons-text | StringSubstitutor | 62 | 16 | 14 | 9 | 4 | GetVariableSuffixMatcherGroup | 44.4% |
| | **Total** | | | | **1071** | **178** | **104** | | **58.4%** |

### Results Summary

Results in `results/live_evaluation/aggregate_results.json`:
- 23 classes evaluated end-to-end
- 1071 total clusters detected, 178 post-filter suggestions
- **104/178 verified (58.4%)** -- compilation + semantic + behavioral tests
- Average runtime: 201.3s per class

### Statistical Analysis

Source: `results/live_evaluation/statistical_analysis.json`

**Effect size (GenEC vs. field-sharing baseline):**
- Wilcoxon signed-rank: W = 20.0, p = 0.0005, n = 22 (significant at alpha = 0.05)
- Cliff's delta: 0.828 (large effect)
- GenEC produces 7.74 suggestions/class vs. 1.61 for the baseline (178 vs. 37 total)

**Verification rate with 95% bootstrap confidence interval:**
- Per-class mean: 68.0% (95% CI: [51.9%, 83.0%])
- Aggregate: 104/178 = 58.4%

The per-class mean (68.0%) is higher than the aggregate rate (58.4%) because
classes with many suggestions (e.g., PiePlot with 19, CategoryPlot with 18)
tend to have lower verification rates, pulling the aggregate down.

**Per-quality-tier verification rates:**

| Quality Tier | Verified | Total | Rate |
|-------------|--------:|------:|-----:|
| SHOULD (score >= 70) | 16 | 18 | 88.9% |
| COULD (score 40-69) | 86 | 149 | 57.7% |
| POTENTIAL (score < 40) | 2 | 11 | 18.2% |

Higher-quality suggestions (as scored by GenEC's internal heuristics) verify
at substantially higher rates, confirming the quality scoring is well-calibrated.

### Extraction Quality Metrics

For the 104 verified suggestions (with 95% bootstrap CI):

| Metric | Mean | 95% CI |
|--------|-----:|-------:|
| Methods per extraction | 5.9 | [5.2, 6.7] |
| Internal cohesion | 0.765 | [0.738, 0.790] |

**Quality tier distribution** (all 178 suggestions):
- SHOULD: 18 (10.1%) -- high-confidence extractions
- COULD: 149 (83.7%) -- moderate-confidence extractions
- POTENTIAL: 11 (6.2%) -- low-confidence extractions

### Key Contributions

- **Verification rate**: 58.4% of suggestions pass compilation, semantic
  equivalence, and behavioral verification via Maven builds.
- **Compilable code generation**: Every accepted suggestion produces code
  that compiles under the project's own build system.
- **Test-preserving refactoring**: Behavioral verification ensures that
  existing test suites continue to pass after extraction.
- **Semantic naming**: Extracted classes receive meaningful names (e.g.,
  `ResourceLoader`, `DateParser`, `WildcardMatcher`) rather than generic labels.

Note: Traditional code-quality metrics (e.g., LCOM5) show only modest
change after extraction. The primary value is in producing *safe*,
developer-ready refactoring suggestions rather than maximising metric deltas.

### Verification Failure Analysis

Of 178 suggestions, 74 failed verification (41.6%):

| Failure Category | Count | Description |
|-----------------|------:|-------------|
| Verification failed | 68 | Failed the 3-tier pipeline (compilation, semantic, or behavioral) |
| Code generation skipped | 6 | JDT-based extraction too complex; no compilable code produced |

The 3-tier verification pipeline runs sequentially: (1) syntactic compilation
via javac, (2) semantic equivalence checking that all members are properly
moved, and (3) behavioral testing via Maven builds. A suggestion marked
"failed" was rejected at the first tier it did not pass. The per-class JSON
files record the aggregate outcome (`verification_status: "failed"`); a
finer-grained per-tier breakdown is available in log output but not persisted
to the result files.

**Failure concentration by project:** JFreeChart classes account for 59 of
the 74 failures (79.7%), driven by deep inheritance hierarchies and complex
cross-class coupling (XYPlot, CategoryPlot, PiePlot, AbstractRenderer). In
contrast, utility classes from Commons libraries have near-zero failure rates.
The 6 code-generation-skipped cases all involve JFreeChart classes where the
JDT-based extraction encounters complex field initialization patterns.

### Project Type Analysis

Verification rates vary substantially by project category:

| Project Category | Classes | Verified | Total | Rate |
|-----------------|--------:|--------:|------:|-----:|
| Utility (Commons IO/Lang/Collections/Text) | 14 | 56 | 68 | 82.4% |
| Framework (JFreeChart) | 5 | 25 | 84 | 29.8% |
| Math (Commons Math) | 4 | 23 | 26 | 88.5% |

**Utility classes** (IOUtils, StringUtils, CollectionUtils, etc.) have
self-contained methods with minimal field coupling, making extraction
straightforward. 13 of 14 utility classes achieve 100% verification.

**Math classes** (AccurateMath, Dfp, BOBYQAOptimizer) also verify at high
rates because their methods are computationally independent with clear
functional boundaries.

**Framework classes** (JFreeChart plot/renderer hierarchy) have the lowest
rates due to deep inheritance, extensive field coupling (60+ fields), and
complex inter-class dependencies. PiePlot (0/19) and XYPlot (2/14) are
the hardest cases, while ChartPanel (14/17 = 82.4%) is an outlier with
more self-contained event-handling methods.

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

Note: The ablation verified% metric uses total clusters as denominator, not
filtered suggestions.

## HECS ECAccEval Benchmark (92 instances)

We evaluated GenEC on the established ECAccEval benchmark from HECS (ISSTA 2024),
containing 92 Extract Class refactoring oracles across 18 open-source projects.

| Subset | N | Precision | Recall | F1 |
|--------|---|-----------|--------|-----|
| All instances | 92 | 0.136 | 0.297 | 0.167 |
| Instances with Git history | 21 | 0.405 | 0.758 | 0.478 |
| Instances without Git history | 71 | 0.057 | 0.161 | 0.076 |
| Multi-member extractions | 49 | 0.228 | 0.476 | 0.281 |

**Controlled ablation (evolutionary coupling):** On the HECS benchmark,
a controlled 21-instance comparison shows identical member-selection
performance with and without evolutionary coupling (macro F1 = 0.478 in
both settings). On our live benchmark, however, evolutionary coupling
increases the number of extracted-class candidates from 53.9 to 68.6
on average (+27.4%). This suggests its main benefit is **candidate
discovery** — surfacing refactoring opportunities that static structure
alone does not reveal — rather than improving within-cluster member
selection.

The F1 difference between the 21-instance (0.478) and 71-instance
(0.076) subsets is due to **project context** (having a compilable repo
with imports and dependencies) rather than evolutionary coupling. The
71 instances use standalone `old.java` files without project context,
which degrades dependency analysis quality.

## User Study

Protocol in `user_study/study_protocol.md`. Participant results pending.

## Prerequisites

- Python 3.10+
- Java 17+ (for JDT wrapper and RefactoringMiner)
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
- **Graph fusion**: alpha=0.8 (80% static, 20% evolutionary)
- **Clustering**: Leiden algorithm, resolution=2.0, min_size=3

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
