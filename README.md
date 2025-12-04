# GenEC: Generative Extract Class Refactoring Framework

A hybrid framework for automated Extract Class refactoring in Java that combines static dependency analysis, evolutionary coupling from Git history, and constrained LLM interaction with multi-layer verification.

## Features

- **Static Dependency Analysis**: Parses Java AST to extract method calls and field accesses
- **Evolutionary Coupling Mining**: Analyzes Git history to identify co-changing methods
- **Graph Fusion**: Combines static and evolutionary dependencies into unified graph
- **Cluster Detection**: Uses Louvain algorithm to identify cohesive method groups
- **LLM-Guided Refactoring**: Generates refactoring suggestions using Claude Sonnet 4
- **Multi-Layer Verification**: Validates refactorings syntactically, semantically, and behaviorally
- **Transactional Application**: Applies changes atomically with automatic rollback on failure
- **Git Integration**: Creates feature branches and atomic commits for each refactoring
- **Dry-Run & Preview**: Generates unified diffs and previews before applying changes

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

### Basic Usage

```python
from genec.core.pipeline import GenECPipeline

# Initialize pipeline
pipeline = GenECPipeline('config/config.yaml')

# Run on a single Java class
result = pipeline.run_full_pipeline(
    class_file='src/main/java/com/example/GodClass.java',
    repo_path='/path/to/git/repo'
)

# View suggestions
for suggestion in result.suggestions:
    print(f"New Class: {suggestion.proposed_class_name}")
    print(f"Rationale: {suggestion.rationale}")
    print(f"Code:\n{suggestion.new_class_code}")
```

### Command Line

```bash
# Run pipeline on a single class
python scripts/run_pipeline.py \
  --class-file path/to/Class.java \
  --repo-path path/to/repo \
  --config config/config.yaml

# Evaluate on ground truth dataset
python scripts/evaluate_all.py \
  --ground-truth data/ground_truth/refactorings.json \
  --output data/outputs/evaluation.json
```

## Architecture

```
genec/
├── core/
│   ├── dependency_analyzer.py    # Static Java analysis
│   ├── evolutionary_miner.py     # Git history mining
│   ├── graph_builder.py          # Graph construction & fusion
│   ├── cluster_detector.py       # Louvain clustering
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

1. **Dependency Analysis**: Extract method calls, field accesses from Java AST
2. **Evolutionary Mining**: Analyze Git history for co-changing methods
3. **Graph Building**: Create and fuse static + evolutionary graphs
4. **Cluster Detection**: Apply Louvain algorithm, filter and rank clusters
   - **Extraction Validation**: Static analysis for abstract methods, inner classes, private dependencies
   - **Auto-fix**: Iterative transitive closure for missing private method dependencies
   - **LLM Semantic Validation**: Intelligent override for borderline cases (confidence >= 0.7)
5. **LLM Generation**: Generate refactoring suggestions via Claude API
6. **Verification**: Validate through syntactic, semantic, behavioral layers
7. **Transformation Guidance** (for rejected clusters):
   - **Pattern Suggestions**: Design patterns to enable blocked extractions
   - **Structural Plans**: Accessor/facade scaffolding for complex changes

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
