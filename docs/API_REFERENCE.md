# GenEC API Reference

This document provides detailed API documentation for GenEC's core modules and classes.

## Table of Contents

- [Configuration](#configuration)
- [Pipeline](#pipeline)
- [Core Components](#core-components)
  - [Dependency Analyzer](#dependency-analyzer)
  - [Evolutionary Miner](#evolutionary-miner)
  - [Graph Builder](#graph-builder)
  - [Cluster Detector](#cluster-detector)
  - [LLM Interface](#llm-interface)
  - [Code Generator](#code-generator)
  - [Verification Engine](#verification-engine)
  - [Refactoring Applicator](#refactoring-applicator)

---

## Configuration

### `GenECConfig`

Type-safe configuration model using Pydantic.

```python
from genec.config import GenECConfig, load_config

# Load from file
config = load_config('config/config.yaml')

# Create programmatically
config = GenECConfig(
    fusion={'alpha': 0.7},
    clustering={'min_cluster_size': 5}
)
```

#### Configuration Sections

**Fusion Configuration** (`config.fusion`)
- `alpha` (float, 0-1): Weight for static dependencies vs evolutionary coupling
- `edge_threshold` (float, 0-1): Minimum edge weight to keep in fused graph

**Evolution Configuration** (`config.evolution`)
- `window_months` (int): Number of months of Git history to analyze
- `min_commits` (int): Minimum commits required for coupling analysis

**Clustering Configuration** (`config.clustering`)
- `algorithm` (str): Clustering algorithm ('louvain', 'leiden', 'spectral')
- `min_cluster_size` (int): Minimum members in cluster
- `max_cluster_size` (int): Maximum members in cluster
- `min_cohesion` (float, 0-1): Minimum cohesion score
- `resolution` (float): Resolution parameter for Louvain

**LLM Configuration** (`config.llm`)
- `provider` (str): LLM provider ('anthropic', 'openai')
- `model` (str): Model identifier
- `max_tokens` (int, 1-200000): Maximum tokens in response
- `temperature` (float, 0-1): Sampling temperature
- `timeout` (int): Request timeout in seconds

**Code Generation Configuration** (`config.code_generation`)
- `engine` (str): Code generation engine ('eclipse_jdt', 'template')
- `jdt_wrapper_jar` (str): Path to JDT wrapper JAR
- `timeout` (int): Timeout in seconds

**Verification Configuration** (`config.verification`)
- `enable_syntactic` (bool): Enable syntactic verification
- `enable_semantic` (bool): Enable semantic verification
- `enable_behavioral` (bool): Enable behavioral verification
- `java_compiler` (str): Java compiler command
- `maven_command` (str): Maven command
- `gradle_command` (str): Gradle command
- `max_workers` (int): Maximum parallel workers

---

## Pipeline

### `GenECPipeline`

Main orchestration class for the GenEC refactoring pipeline.

```python
from genec.core.pipeline import GenECPipeline

# Initialize with config file
pipeline = GenECPipeline('config/config.yaml')

# Run full pipeline
result = pipeline.run_full_pipeline(
    class_file='path/to/MyClass.java',
    repo_path='path/to/repo',
    max_suggestions=3,
    auto_apply=False
)
```

#### Methods

##### `__init__(config_file: str = 'config/config.yaml')`

Initialize the pipeline with configuration.

**Parameters:**
- `config_file` (str): Path to YAML configuration file

**Raises:**
- `FileNotFoundError`: If JDT wrapper JAR not found
- `ValueError`: If configuration is invalid

##### `run_full_pipeline(class_file, repo_path, max_suggestions=3, auto_apply=False)`

Execute the complete GenEC pipeline.

**Parameters:**
- `class_file` (str): Path to Java class file to analyze
- `repo_path` (str): Path to repository root
- `max_suggestions` (int): Maximum refactoring suggestions to generate
- `auto_apply` (bool): Automatically apply verified refactorings

**Returns:**
- `PipelineResult`: Contains suggestions, clusters, metrics, and applied refactorings

**Raises:**
- `FileNotFoundError`: If class file doesn't exist
- `ValueError`: If file is not a .java file
- `CodeGenerationError`: If code generation fails

##### `check_prerequisites()`

Check availability of required tools.

**Returns:**
- `dict`: Tool names mapped to availability status

---

## Core Components

### Dependency Analyzer

Analyzes static dependencies in Java classes using Eclipse JDT.

```python
from genec.core.dependency_analyzer import DependencyAnalyzer

analyzer = DependencyAnalyzer()
class_deps = analyzer.analyze_java_class('MyClass.java', 'path/to/repo')
```

#### `DependencyAnalyzer`

##### `analyze_java_class(class_file: str, repo_path: str) -> ClassDependencies`

Analyze dependencies in a Java class.

**Parameters:**
- `class_file` (str): Path to Java source file
- `repo_path` (str): Repository root path

**Returns:**
- `ClassDependencies`: Object containing dependency information

#### `ClassDependencies`

Dataclass containing class dependency information.

**Attributes:**
- `class_name` (str): Name of the class
- `methods` (List[MethodInfo]): List of methods
- `fields` (List[FieldInfo]): List of fields
- `member_names` (List[str]): All member names (methods + fields)
- `dependency_matrix` (List[List[int]]): Dependency strength matrix
- `method_calls` (Dict[str, List[str]]): Method call graph
- `field_accesses` (Dict[str, List[str]]): Field access information

**Methods:**
- `get_all_methods() -> List[MethodInfo]`: Get all methods
- `get_all_fields() -> List[FieldInfo]`: Get all fields

---

### Evolutionary Miner

Mines evolutionary coupling from Git history.

```python
from genec.core.evolutionary_miner import EvolutionaryMiner

miner = EvolutionaryMiner(cache_dir='data/cache')
evo_data = miner.mine_method_cochanges(
    'src/MyClass.java',
    '/path/to/repo',
    window_months=12,
    min_commits=2
)
```

#### `EvolutionaryMiner`

##### `mine_method_cochanges(class_file, repo_path, window_months=12, min_commits=2) -> EvolutionaryData`

Mine method co-change patterns from Git history.

**Parameters:**
- `class_file` (str): Relative path to class file from repo root
- `repo_path` (str): Repository root path
- `window_months` (int): Months of history to analyze
- `min_commits` (int): Minimum commits for coupling

**Returns:**
- `EvolutionaryData`: Co-change patterns

---

### Graph Builder

Builds and fuses static and evolutionary dependency graphs.

```python
from genec.core.graph_builder import GraphBuilder

builder = GraphBuilder()

# Build static graph
G_static = builder.build_static_graph(class_deps)

# Build evolutionary graph
G_evo = builder.build_evolutionary_graph(evo_data)

# Fuse graphs
G_fused = builder.fuse_graphs(G_static, G_evo, alpha=0.5)
```

#### `GraphBuilder`

##### `build_static_graph(class_deps: ClassDependencies) -> nx.Graph`

Build static dependency graph.

**Returns:**
- NetworkX graph with weighted edges

##### `build_evolutionary_graph(evo_data: EvolutionaryData) -> nx.Graph`

Build evolutionary coupling graph.

**Returns:**
- NetworkX graph with weighted edges

##### `fuse_graphs(G_static, G_evo, alpha=0.5, edge_threshold=0.1) -> nx.Graph`

Fuse static and evolutionary graphs.

**Parameters:**
- `alpha` (float): Weight for static graph (0.5 = equal weight)
- `edge_threshold` (float): Minimum edge weight

**Returns:**
- Fused graph

---

### Cluster Detector

Detects and ranks refactoring candidate clusters using community detection.

```python
from genec.core.cluster_detector import ClusterDetector

detector = ClusterDetector(
    min_cluster_size=3,
    max_cluster_size=15,
    min_cohesion=0.5,
    resolution=1.0
)

clusters = detector.detect_clusters(G_fused, class_deps)
```

#### `ClusterDetector`

##### `detect_clusters(graph: nx.Graph, class_deps: ClassDependencies) -> List[Cluster]`

Detect refactoring candidate clusters.

**Returns:**
- List of Cluster objects

##### `filter_clusters(clusters: List[Cluster]) -> List[Cluster]`

Filter clusters by size and cohesion.

##### `rank_clusters(clusters: List[Cluster], class_deps: ClassDependencies) -> List[Cluster]`

Rank clusters by cohesion score.

---

### LLM Interface

Interface for LLM-powered refactoring suggestions.

```python
from genec.core.llm_interface import LLMInterface

llm = LLMInterface(
    api_key='your-api-key',
    model='claude-sonnet-4-20250514',
    max_tokens=4000
)

suggestions = llm.generate_suggestions(
    cluster,
    class_deps,
    original_code,
    max_suggestions=3
)
```

#### `LLMInterface`

##### `generate_suggestions(cluster, class_deps, original_code, max_suggestions=3) -> List[RefactoringSuggestion]`

Generate refactoring suggestions for a cluster.

**Returns:**
- List of RefactoringSuggestion objects

#### `RefactoringSuggestion`

Dataclass representing a refactoring suggestion.

**Attributes:**
- `proposed_class_name` (str): Name for extracted class
- `rationale` (str): Explanation of refactoring
- `cluster` (Cluster): Source cluster
- `new_class_code` (str): Generated code for new class
- `modified_original_code` (str): Modified original class

---

### Code Generator

Generates refactored code using Eclipse JDT.

```python
from genec.core.jdt_code_generator import JDTCodeGenerator

generator = JDTCodeGenerator(
    jdt_wrapper_jar='path/to/jar',
    timeout=60
)

generated = generator.generate(
    cluster,
    'NewClassName',
    'MyClass.java',
    '/path/to/repo',
    class_deps
)
```

#### `JDTCodeGenerator`

##### `generate(cluster, new_class_name, class_file, repo_path, class_deps) -> GeneratedCode`

Generate refactored code.

**Returns:**
- `GeneratedCode`: Object with new_class_code and modified_original_code

**Raises:**
- `CodeGenerationError`: If JDT refactoring fails

---

### Verification Engine

Verifies refactoring correctness.

```python
from genec.core.verification_engine import VerificationEngine

verifier = VerificationEngine(
    enable_syntactic=True,
    enable_semantic=True,
    enable_behavioral=True,
    repo_path='/path/to/repo'
)

result = verifier.verify_refactoring(
    suggestion,
    original_code,
    'MyClass.java',
    '/path/to/repo',
    class_deps
)
```

#### `VerificationEngine`

##### `verify_refactoring(suggestion, original_code, class_file, repo_path, class_deps) -> VerificationResult`

Verify a refactoring suggestion.

**Returns:**
- `VerificationResult`: Contains passed checks and error messages

---

### Refactoring Applicator

Applies verified refactorings to the filesystem.

```python
from genec.core.refactoring_applicator import RefactoringApplicator

applicator = RefactoringApplicator(
    create_backups=True,
    backup_dir='.genec_backups'
)

application = applicator.apply_refactoring(
    suggestion,
    'MyClass.java',
    '/path/to/repo',
    dry_run=False
)
```

#### `RefactoringApplicator`

##### `apply_refactoring(suggestion, original_class_file, repo_path, dry_run=False) -> RefactoringApplication`

Apply a refactoring to the filesystem.

**Parameters:**
- `dry_run` (bool): If True, don't write files

**Returns:**
- `RefactoringApplication`: Contains status and file paths

##### `rollback_refactoring(application: RefactoringApplication) -> bool`

Rollback a refactoring by restoring from backup.

**Returns:**
- True if rollback successful

---

## Exception Classes

GenEC defines custom exceptions for different error scenarios:

```python
from genec.exceptions import (
    GenECError,              # Base exception
    ConfigurationError,      # Invalid configuration
    CodeGenerationError,     # Code generation failure
    VerificationError,       # Verification failure
    LLMError,                # LLM-related errors
    LLMServiceUnavailable,   # LLM service down
    LLMRequestFailed,        # LLM request failed
)
```

---

## Usage Examples

### Basic Pipeline Execution

```python
from genec.core.pipeline import GenECPipeline

pipeline = GenECPipeline('config/config.yaml')

result = pipeline.run_full_pipeline(
    class_file='src/main/java/com/example/LargeClass.java',
    repo_path='/path/to/project',
    max_suggestions=3
)

print(f"Found {len(result.suggestions)} suggestions")
for suggestion in result.verified_suggestions:
    print(f"- {suggestion.proposed_class_name}: {suggestion.rationale}")
```

### Custom Configuration

```python
from genec.config import GenECConfig
from genec.core.pipeline import GenECPipeline

# Create custom config
config = GenECConfig(
    fusion={'alpha': 0.8},  # Favor static dependencies
    clustering={
        'min_cluster_size': 5,
        'max_cluster_size': 20,
        'min_cohesion': 0.6
    },
    llm={
        'model': 'claude-sonnet-4-20250514',
        'temperature': 0.2
    }
)

# Save to file
from genec.config import save_config
save_config(config, 'custom_config.yaml')

# Use in pipeline
pipeline = GenECPipeline('custom_config.yaml')
```

### Programmatic Access to Components

```python
from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.graph_builder import GraphBuilder
from genec.core.cluster_detector import ClusterDetector

# Analyze dependencies
analyzer = DependencyAnalyzer()
class_deps = analyzer.analyze_java_class('MyClass.java', '/repo')

# Build graph
builder = GraphBuilder()
G = builder.build_static_graph(class_deps)

# Detect clusters
detector = ClusterDetector()
clusters = detector.detect_clusters(G, class_deps)
clusters = detector.filter_clusters(clusters)
clusters = detector.rank_clusters(clusters, class_deps)

# Top cluster
best_cluster = clusters[0]
print(f"Best cluster: {best_cluster.member_names}")
print(f"Cohesion: {best_cluster.cohesion_score:.2f}")
```

---

## Type Definitions

GenEC uses type hints throughout. Key types:

```python
from typing import List, Dict, Optional, Set, Tuple
import networkx as nx

# Common types
ClassFile = str  # Path to Java class file
RepoPath = str   # Path to repository root
MemberName = str # Method signature or field name
ClusterId = int  # Cluster identifier
```

---

For more information, see:
- [Architecture Documentation](ARCHITECTURE.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
