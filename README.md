# GenEC: Generative Extract Class Refactoring Framework

A hybrid framework for automated Extract Class refactoring in Java that combines static dependency analysis, evolutionary coupling from Git history, and constrained LLM interaction with multi-layer verification.

## Features

- **Static Dependency Analysis**: Parses Java AST to extract method calls and field accesses
- **Evolutionary Coupling Mining**: Analyzes Git history to identify co-changing methods
- **Graph Fusion**: Combines static and evolutionary dependencies into unified graph
- **Cluster Detection**: Uses Leiden algorithm to identify cohesive method groups
- **LLM-Guided Refactoring**: Generates refactoring suggestions using Claude Sonnet 4
- **Multi-Layer Verification**: Validates refactorings syntactically, semantically, and behaviorally
- **Transactional Application**: Applies changes atomically with automatic rollback on failure
- **Git Integration**: Creates feature branches and atomic commits for each refactoring
- **Dry-Run & Preview**: Generates unified diffs and previews before applying changes

## Prerequisites

- **Python 3.10+**
- **Java 17+** (for the JDT code generation wrapper)
- **Git** (required for evolutionary coupling analysis)
- **Maven** (optional, needed for behavioral verification)

## Installation

```bash
cd genec
pip install -e .
```

## Configuration

Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Or pass it directly via `--api-key` on the command line.

Edit `config/config.yaml` to customize parameters.

### Validation Configuration

The pipeline includes three-tier validation that prevents invalid extractions:

```yaml
verification:
  enable_extraction_validation: true     # Static analysis before code generation
  suggest_pattern_transformations: true  # LLM design pattern suggestions
  enable_semantic: true                  # Semantic AST validation

refactoring_application:
  enabled: true
  dry_run: false                         # Set to true to preview only
  auto_apply: true                       # Automatically apply verified suggestions
  enable_git: true                       # Create branches and commits
  transactional: true                    # All-or-nothing application
  backup: true                           # Create filesystem backups
```

**Validation Tiers**:
1. **Static Validation** (~instant): Detects abstract methods, inner classes, missing private dependencies
2. **LLM Semantic** (~3-5s per cluster): Validates borderline cases, overrides if confidence >= 0.7
3. **Pattern Transformation** (~3-5s per cluster): Suggests design patterns to enable blocked extractions

**Output**:
- Valid suggestions → `data/outputs/{ClassName}/suggestion_{N}/`
- Pattern guidance → `data/outputs/{ClassName}/transformation_guidance/`
- Structural plans → `data/outputs/structural_plans/{ClassName}/`

## Usage

### Command Line

```bash
# Basic usage
genec --target path/to/Class.java --repo path/to/repo

# Preview changes without applying them
genec --target path/to/Class.java --repo path/to/repo --dry-run

# JSON output (for tool integration)
genec --target path/to/Class.java --repo path/to/repo --json

# Save reports and use LLM cache for reproducibility
genec --target path/to/Class.java --repo path/to/repo \
  --report-dir ./reports --cache-dir ./cache --use-cache
```

#### CLI Flags

| Flag | Description |
|------|-------------|
| `--target` | **(required)** Path to the Java class file to refactor |
| `--repo` | **(required)** Path to the repository root |
| `--config` | Path to config file (default: `config/config.yaml`) |
| `--dry-run` | Show what would be applied without making changes |
| `--json` | Output results in JSON format |
| `--api-key` | Anthropic API key (overrides `ANTHROPIC_API_KEY` env var) |
| `--report-dir` | Directory to save pipeline reports |
| `--cache-dir` | Directory for LLM response cache (reproducibility) |
| `--use-cache` | Use cached LLM responses if available |
| `--max-suggestions` | Maximum number of suggestions (default: 5) |
| `--apply-all` | Automatically apply all verified refactorings |
| `--verbose` | Enable DEBUG-level logging |
| `--min-cluster-size` | Override minimum cluster size |
| `--max-cluster-size` | Override maximum cluster size |
| `--min-cohesion` | Override minimum cohesion threshold |
| `--check-coverage` | Verify test coverage of extracted classes (requires JaCoCo) |
| `--seed INT` | Random seed for reproducible clustering |
| `--max-passes INT` | Maximum decomposition passes (default: 1) |
| `--no-build` | Disable automatic building of dependencies |
| `--websocket PORT` | Enable WebSocket progress server on the given port |
| `--multi-file` | Enable multi-file dependency analysis mode |

### Python API

```python
from genec.core.pipeline import GenECPipeline

# Initialize pipeline
pipeline = GenECPipeline('config/config.yaml')

# Run on a single Java class
result = pipeline.run_full_pipeline(
    class_file='src/main/java/com/example/GodClass.java',
    repo_path='/path/to/git/repo'
)

# View verified suggestions
for suggestion in result.verified_suggestions:
    print(f"New Class: {suggestion.proposed_class_name}")
    print(f"Rationale: {suggestion.rationale}")
    print(f"Confidence: {suggestion.confidence_score}")
    print(f"Code:\n{suggestion.new_class_code}")
```

## Architecture

```
genec/
├── core/
│   ├── stages/                   # Pipeline stages
│   │   ├── analysis_stage.py
│   │   ├── clustering_stage.py
│   │   ├── graph_processing_stage.py
│   │   ├── naming_stage.py
│   │   └── refactoring_stage.py
│   ├── pipeline_runner.py        # Pipeline orchestrator
│   ├── dependency_analyzer.py    # Static Java analysis
│   ├── evolutionary_miner.py     # Git history mining
│   ├── graph_builder.py          # Graph construction & fusion
│   ├── cluster_detector.py       # Leiden clustering
│   ├── llm_interface.py          # Claude API integration
│   ├── verification_engine.py    # Multi-layer verification
│   └── pipeline.py               # Main orchestration
├── llm/
│   ├── anthropic_client.py       # Centralized LLM client with retry
│   └── __init__.py               # LLM utilities
├── parsers/
│   └── java_parser.py            # Java AST parsing
├── metrics/
│   ├── cohesion_calculator.py    # LCOM5 calculation
│   └── coupling_calculator.py    # CBO calculation
├── verification/
│   ├── extraction_validator.py   # Static extraction validation
│   ├── llm_semantic_validator.py # LLM-based semantic validation
│   ├── llm_pattern_transformer.py # Design pattern suggestions
│   ├── syntactic_verifier.py     # Compilation checks
│   ├── semantic_verifier.py      # AST validation
│   └── behavioral_verifier.py    # Test execution
├── structural/
│   ├── transformer.py            # Structural scaffolding plans
│   └── compile_validator.py     # Build validation
└── evaluation/
    ├── ground_truth_builder.py   # RefactoringMiner integration
    └── comparator.py             # Precision/Recall/F1
```

## Pipeline Stages

1.  **AnalysisStage**: Extract method calls, field accesses from Java AST and analyze Git history for co-changing methods.
2.  **GraphProcessingStage**: Create and fuse static + evolutionary graphs, calculate metrics, and export data.
3.  **ClusteringStage**: Apply Leiden algorithm, filter and rank clusters.
    - **Extraction Validation**: Static analysis for abstract methods, inner classes, private dependencies
    - **Auto-fix**: Iterative transitive closure for missing private method dependencies
    - **LLM Semantic Validation**: Intelligent override for borderline cases (confidence >= 0.7)
4.  **NamingStage**: Generate refactoring suggestions via Claude API (LLM).
5.  **RefactoringStage**: Apply and verify refactorings.
    - **Verification**: Validate through syntactic, semantic, behavioral layers
    - **Transformation Guidance** (for rejected clusters): Pattern suggestions and structural plans

## Metrics

- **LCOM5**: Lack of Cohesion of Methods (lower is better)
- **CBO**: Coupling Between Objects (lower is better)
- **Modularity**: Graph modularity score (higher is better)
- **Precision/Recall/F1**: Against ground truth refactorings

## Testing

```bash
pytest tests/
```

## Documentation

- **[Architecture Guide](docs/ARCHITECTURE.md)**: Detailed architecture documentation including the three-tier validation system
- **[Developer Guide](docs/DEVELOPER_GUIDE.md)**: Guide for extending GenEC and adding new validation rules

## License

MIT License
