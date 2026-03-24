# GenEC Artifact

## Quick Start

### Option 1: Docker (recommended)
```bash
docker build -t genec .
docker run genec --help
```

### Option 2: Local
```bash
./reproduce.sh
```

## Artifact Contents

| Directory | Contents |
|-----------|----------|
| `genec/` | Core Python framework (16K LOC) |
| `genec-jdt-wrapper/` | Eclipse JDT code generator (Java) |
| `vscode-extension/` | VS Code IDE integration |
| `evaluation/` | Evaluation scripts, baselines, results |
| `tests/` | 358 automated tests |
| `config/` | Default configuration |

## Pre-computed Results

All evaluation results are committed for reproducibility:
- `evaluation/results/live_evaluation/` — 23-class benchmark
- `evaluation/results/hecs/` — 92-instance HECS benchmark
- `evaluation/results/ablation_results.json` — Ablation study
- `evaluation/results/baseline_results.json` — Baseline comparison

## Reproducing Results

See `reproduce.sh` for the complete reproduction script.
Note: LLM-based naming requires an Anthropic API key (~$5-10 per full run).
All other components (clustering, verification, baselines) work without API credits.

## Requirements

- Python 3.10+
- Java 17+
- Maven 3.6+
- Git
- (Optional) Anthropic API key for LLM naming
