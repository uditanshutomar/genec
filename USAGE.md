# GenEC Usage Guide

## Installation

```bash
cd genec
pip install -e .
```

## Configuration

1. Set your Anthropic API key:
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

2. Edit `config/config.yaml` to customize parameters:
   - Graph fusion weights
   - Clustering parameters
   - LLM settings
   - Verification options

## Basic Usage

### Running on a Single Class

```python
from genec.core.pipeline import GenECPipeline

# Initialize pipeline
pipeline = GenECPipeline('config/config.yaml')

# Run on a Java class
result = pipeline.run_full_pipeline(
    class_file='src/main/java/com/example/GodClass.java',
    repo_path='/path/to/git/repo'
)

# View results
for suggestion in result.verified_suggestions:
    print(f"Suggested class: {suggestion.proposed_class_name}")
    print(f"Rationale: {suggestion.rationale}")
    print(f"Members: {suggestion.cluster.member_names}")
```

### Command Line Usage

```bash
# Run pipeline
python scripts/run_pipeline.py \
  --class-file path/to/GodClass.java \
  --repo-path path/to/repo \
  --max-suggestions 5 \
  --output-dir data/outputs

# Evaluate against ground truth
python scripts/evaluate_all.py \
  --ground-truth data/ground_truth/refactorings.json \
  --repo-path path/to/repo \
  --output data/outputs/evaluation.json
```

## Advanced Usage

### Custom Configuration

```python
from genec.core.pipeline import GenECPipeline

# Load custom config
pipeline = GenECPipeline('my_config.yaml')

# Override specific settings
pipeline.cluster_detector.min_cluster_size = 2
pipeline.verification_engine.enable_behavioral = False

# Run pipeline
result = pipeline.run_full_pipeline(class_file, repo_path)
```

### Using Individual Components

```python
from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector

# Analyze dependencies
analyzer = DependencyAnalyzer()
class_deps = analyzer.analyze_class('MyClass.java')

# Build graph
builder = GraphBuilder()
graph = builder.build_static_graph(class_deps)

# Detect clusters
detector = ClusterDetector(min_cluster_size=3)
clusters = detector.detect_clusters(graph)

# View clusters
for cluster in clusters:
    print(f"Cluster {cluster.id}: {cluster.member_names}")
```

### Calculating Metrics

```python
from genec.metrics.cohesion_calculator import CohesionCalculator
from genec.metrics.coupling_calculator import CouplingCalculator

cohesion_calc = CohesionCalculator()
coupling_calc = CouplingCalculator()

# Calculate LCOM5
lcom5 = cohesion_calc.calculate_lcom5(class_deps)
print(f"LCOM5: {lcom5:.3f}")

# Calculate CBO
cbo = coupling_calc.calculate_cbo(class_deps)
print(f"CBO: {cbo}")
```

### Running Baselines

```python
from genec.baselines.bavota_baseline import BavotaBaseline
from genec.baselines.naive_llm_baseline import NaiveLLMBaseline

# Bavota baseline
bavota = BavotaBaseline()
suggestions = bavota.run('MyClass.java')

# Naive LLM baseline
naive_llm = NaiveLLMBaseline()
suggestions = naive_llm.run('MyClass.java')
```

## Pipeline Stages

1. **Dependency Analysis**: Parses Java AST to extract methods, fields, and dependencies
2. **Evolutionary Mining**: Analyzes Git history for method co-changes
3. **Graph Building**: Creates and fuses static + evolutionary graphs
4. **Cluster Detection**: Applies Louvain algorithm to find cohesive groups
5. **LLM Generation**: Generates refactoring suggestions via Claude API
6. **Verification**: Validates suggestions (syntactic, semantic, behavioral)

## Output

The pipeline produces:

- **Verified Suggestions**: Refactorings that passed all verification layers
- **New Class Code**: Complete Java code for extracted classes
- **Modified Original Code**: Updated original class with delegation
- **Metrics**: Quality metrics (LCOM5, CBO, etc.)
- **Cluster Information**: Details about detected clusters

## Verification Layers

### Layer 1: Syntactic Verification
- Compiles both the new class and modified original class
- Ensures code is syntactically correct

### Layer 2: Semantic Verification
- Validates that refactoring is a proper Extract Class transformation
- Checks that extracted members exist in original
- Verifies no unexpected member loss

### Layer 3: Behavioral Verification
- Creates a copy of the project
- Applies the refactoring
- Runs the test suite
- Ensures all tests still pass

## Tips for Best Results

1. **Use classes with low cohesion**: GenEC works best on "god classes" with multiple responsibilities
2. **Ensure Git history**: Evolutionary coupling requires commit history
3. **Have comprehensive tests**: Behavioral verification needs a test suite
4. **Adjust clustering parameters**: Fine-tune `min_cluster_size` and `max_cluster_size`
5. **Review suggestions**: Always review LLM-generated code before applying

## Troubleshooting

### No clusters detected
- Class may already be well-designed
- Try lowering `min_cluster_size` in config
- Check if graph has enough edges

### Verification failures
- Ensure Java compiler (javac) is installed
- Check that build tools (Maven/Gradle) are available
- Review error messages in logs

### LLM errors
- Verify API key is set correctly
- Check network connectivity
- Review rate limits

### Performance issues
- Enable caching in config
- Reduce `window_months` for evolutionary mining
- Limit `max_suggestions` parameter
