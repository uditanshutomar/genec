# GenEC Architecture Documentation

## Overview

GenEC is a hybrid framework for automated Extract Class refactoring that combines static analysis, evolutionary coupling mining, and LLM-guided code generation with multi-tier validation to ensure safe, meaningful refactorings.

## High-Level Architecture

GenEC uses a modular **Pipeline Architecture** orchestrated by a `PipelineRunner`. The process is divided into distinct, sequential **Stages**, each responsible for a specific phase of the refactoring lifecycle.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PipelineRunner                                │
│                                                                         │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐             │
│  │ AnalysisStage│──▶│GraphProcessing   │──▶│Clustering    │             │
│  │              │   │Stage             │   │Stage         │             │
│  └──────┬───────┘   └────────┬─────────┘   └──────┬───────┘             │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌──────────────┐             │
│  │Refactoring   │◀──│NamingStage       │◀──│(Validation)  │             │
│  │Stage         │   │                  │   │              │             │
│  └──────────────┘   └──────────────────┘   └──────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pipeline Stages

1.  **AnalysisStage**: Performs static dependency analysis (AST) and evolutionary mining (Git history).
2.  **GraphProcessingStage**: Fuses static and evolutionary graphs, calculates centrality metrics, and exports graph data.
3.  **ClusteringStage**: Detects communities (clusters) using Louvain algorithm, filters them based on quality tiers, and ranks them.
4.  **NamingStage**: Generates meaningful class names and refactoring suggestions using LLM (Claude).
5.  **RefactoringStage**: Applies refactorings (transactionally) and verifies them using the multi-tier verification engine.

## Core Components

### 0. Pipeline Orchestration

- **PipelineRunner**: Orchestrates the sequential execution of stages.
  - [genec/core/pipeline_runner.py](../genec/core/pipeline_runner.py)
- **PipelineStage**: Abstract base class for all stages.
  - [genec/core/stages/base_stage.py](../genec/core/stages/base_stage.py)

### 1. Analysis Layer

#### Static Dependency Analyzer
- **Purpose**: Extract structural dependencies from Java source code
- **Technology**: Tree-sitter for AST parsing
- **Output**: Dependency graph with method calls and field accesses
- **Key Files**:
  - [genec/core/dependency_analyzer.py](../genec/core/dependency_analyzer.py)
  - [genec/parsers/java_parser.py](../genec/parsers/java_parser.py)

#### Evolutionary Coupling Miner
- **Purpose**: Identify methods that frequently change together
- **Technology**: Git history analysis
- **Output**: Co-change graph weighted by temporal coupling
- **Key Files**: [genec/core/evolutionary_miner.py](../genec/core/evolutionary_miner.py)

#### Graph Fusion
- **Purpose**: Combine static and evolutionary signals
- **Algorithm**: Weighted sum with configurable α parameter
- **Output**: Unified dependency graph for clustering
- **Key Files**: [genec/core/graph_builder.py](../genec/core/graph_builder.py)

### 2. Clustering Layer

#### Louvain Community Detection
- **Purpose**: Identify cohesive method groups
- **Algorithm**: Louvain modularity optimization
- **Filters**: Size constraints, cohesion thresholds
- **Key Files**: [genec/core/cluster_detector.py](../genec/core/cluster_detector.py)

### 3. Validation Layer ⭐ **New**

GenEC uses a **three-tier validation architecture** to ensure only safe, compilable extractions proceed to code generation:

```
                    ┌──────────────────────┐
                    │   Detected Cluster   │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Tier 1: Static      │
                    │  Validation          │
                    │  (~instant)          │
                    │                      │
                    │  • Abstract methods  │
                    │  • Inner classes     │
                    │  • Private deps      │
                    │  • Auto-fix closure  │
                    └──────────┬───────────┘
                               │
                       ┌───────┴────────┐
                       │                │
                  ✓ Valid          ✗ Blocked
                       │                │
                       │     ┌──────────▼───────────┐
                       │     │  Tier 2: LLM         │
                       │     │  Semantic Validation │
                       │     │  (~3-5s)             │
                       │     │                      │
                       │     │  • Context analysis  │
                       │     │  • Pattern detection │
                       │     │  • Confidence score  │
                       │     └──────────┬───────────┘
                       │                │
                       │        ┌───────┴────────┐
                       │        │                │
                       │   Confidence       Confidence
                       │    >= 0.7           < 0.7
                       │        │                │
                       │     Override        Rejected
                       │        │                │
                       └────────┴────┐           │
                                     │    ┌──────▼───────────┐
                    ┌────────────────▼────▼──┐  │  Tier 3:  │
                    │   Code Generation      │  │  Pattern  │
                    │   (LLM + JDT)          │  │  Transform│
                    └────────────────────────┘  │  (~3-5s)  │
                                                │           │
                                                │ • Strategy│
                                                │ • Visitor │
                                                │ • Facade  │
                                                └───────────┘
```

#### Tier 1: Static Extraction Validator

**Purpose**: Prevent invalid extractions using static analysis

**Implementation**: [genec/verification/extraction_validator.py](../genec/verification/extraction_validator.py)

**Detection Rules**:

1. **Abstract Method Calls** (Blocking)
   - Methods in cluster call abstract methods from parent class
   - **Cannot be fixed**: Extracted class can't inherit abstract methods
   - **Action**: Reject cluster

2. **Inner Class References** (Blocking)
   - Methods reference private inner classes
   - **Cannot be fixed**: Inner classes not accessible from extracted class
   - **Action**: Reject cluster

3. **Private Method Dependencies** (Auto-fixable)
   - Methods call private helpers not in cluster
   - **Can be fixed**: Include missing methods via transitive closure
   - **Action**: Auto-include dependencies (up to 10 iterations)

**Auto-fix Algorithm**:
```python
def validate_extraction(cluster, class_deps):
    iteration = 0
    max_iterations = 10
    methods_added = True

    while methods_added and iteration < max_iterations:
        iteration += 1
        methods_added = False

        # Check for missing private method calls
        for method in cluster.methods:
            for called_method in get_called_methods(method):
                if is_private(called_method) and called_method not in cluster:
                    cluster.add(called_method)
                    methods_added = True

        # Check for blocking issues
        if has_abstract_calls(cluster) or has_inner_class_refs(cluster):
            return (False, blocking_issues)

    return (True, [])
```

**Configuration**:
```yaml
verification:
  enable_extraction_validation: true
```

#### Tier 2: LLM Semantic Validator

**Purpose**: Intelligently override conservative static rejections

**Implementation**: [genec/verification/llm_semantic_validator.py](../genec/verification/llm_semantic_validator.py)

**When Used**: Only when Tier 1 rejects a cluster

**Process**:
1. Send cluster context + blocking issues to Claude Sonnet 4
2. LLM analyzes whether extraction can work despite issues
3. Returns confidence score (0.0-1.0) and reasoning
4. Override rejection if confidence >= 0.7

**Example Prompt**:
```
You are a Java refactoring expert. Analyze if this cluster can be safely
extracted despite the following blocking issues:

BLOCKING ISSUES:
- Calls abstract method 'pendingToString()'
- References inner class 'Cancellation'

CLUSTER METHODS:
- get(long, TimeUnit)
- isCancelled()
- tryInternalFastPathGetFailure()

Can this extraction work? Consider:
- Can abstract methods be passed as callbacks?
- Can inner classes be made accessible?
- Are there design patterns that enable this?

Response format:
SAFE_TO_EXTRACT: true/false
CONFIDENCE: 0.0-1.0
REASONING: <explanation>
```

**Configuration**:
```yaml
verification:
  enable_extraction_validation: true
  # LLM validator automatically enabled when static validator is enabled
```

**Performance**: ~3-5 seconds per cluster (uses AnthropicClientWrapper with retry)

#### Tier 3: Pattern Transformation Guidance

**Purpose**: Suggest design patterns to enable blocked extractions

**Implementation**: [genec/verification/llm_pattern_transformer.py](../genec/verification/llm_pattern_transformer.py)

**When Used**: When LLM validator confirms rejection (confidence < 0.7)

**Suggested Patterns**:

| Blocking Issue | Suggested Patterns |
|----------------|-------------------|
| Abstract method dependencies | Strategy Pattern, Template Method |
| Inner class references | Interface Extraction, Visitor Pattern |
| Complex state coupling | Facade, Mediator, Observer |
| Static helper dependencies | Dependency Injection, Service Locator |

**Output Format**:
```
CLUSTER 5 - TRANSFORMATION GUIDANCE
================================================================================

Pattern: Strategy Pattern
Confidence: 0.85

Description:
The cluster calls abstract method 'pendingToString()' which prevents direct
extraction. Apply Strategy Pattern to pass the behavior as a parameter.

Required Modifications:
  1. Extract interface: FutureValueProvider with method pendingToString()
  2. Modify extracted class to accept FutureValueProvider in constructor
  3. Update original class to implement FutureValueProvider
  4. Pass 'this' as provider when calling extracted class methods

Code Structure:
interface FutureValueProvider {
    String pendingToString();
}

class ExtractedFutureOperations {
    private final FutureValueProvider provider;

    ExtractedFutureOperations(FutureValueProvider provider) {
        this.provider = provider;
    }

    Object get(long timeout, TimeUnit unit) {
        // Use provider.pendingToString() instead of direct call
    }
}
```

**Configuration**:
```yaml
verification:
  suggest_pattern_transformations: true
```

### 4. Structural Transformation Layer ⭐ **New**

**Purpose**: Generate template-based scaffolding for complex architectural changes

**Implementation**: [genec/structural/transformer.py](../genec/structural/transformer.py)

**When Used**: When no viable clusters remain after validation, but rejected clusters exist

**Output**: Markdown plans with:
- Extracted members (methods, fields)
- Blocking issues detected
- Inner class interface abstractions
- Accessor interface skeleton
- Helper class skeleton

**Example Output** ([AbstractFuture cluster_02_structural_plan.md](../data/outputs/structural_plans/AbstractFuture/cluster_02_structural_plan.md)):

```markdown
# Structural Refactoring Plan for AbstractFuture – Cluster 2

Generated: 2025-11-05 09:48:49 UTC

## Extracted Members
Methods:
- get(long,TimeUnit)
- isCancelled()
- tryInternalFastPathGetFailure()

## Detected Blocking Issues
- References inner class 'Cancellation' which may not be accessible
- Calls abstract method 'pendingToString()' which cannot be accessed

## Suggested Scaffolding

### Inner Class Abstractions
- Extract interface `CancellationView` exposing required members.

### Proposed Accessor Interface
```java
interface AbstractFutureStateAccessor {
    Object getCurrentValue();
    boolean casValue(Object expect, Object update);
    boolean isDone();
    boolean wasInterrupted();
}
```

### Suggested Helper Skeleton
```java
final class AbstractFutureOperations {
    private final AbstractFutureStateAccessor accessor;

    AbstractFutureOperations(AbstractFutureStateAccessor accessor) {
        this.accessor = accessor;
    }

    // TODO: migrate extracted methods here.
}
```
```

**Size Limits**:
- Max 40 methods per plan (configurable)
- Max 20 fields per plan (configurable)
- Prevents unwieldy plans for very large clusters

**Configuration**:
```yaml
structural_transforms:
  enabled: true
  max_methods: 40
  max_fields: 20
  output_dir: data/outputs/structural_plans
```

### 5. Code Generation Layer

#### LLM Interface
- **Purpose**: Generate meaningful class names and documentation
- **Model**: Claude Sonnet 4
- **Centralized Client**: [genec/llm/anthropic_client.py](../genec/llm/anthropic_client.py)
  - Exponential backoff with jitter
  - Configurable retry (default: 3 attempts)
  - Timeout handling (default: 60s)
  - Prompt truncation (max 16K chars)
- **Key Files**: [genec/core/llm_interface.py](../genec/core/llm_interface.py)

#### Eclipse JDT Wrapper
- **Purpose**: Generate compilable Java code
- **Technology**: Eclipse JDT refactoring engine
- **Features**:
  - Extract Class transformation
  - Field accessor generation
  - Static helper qualification
  - Referenced static field extraction ⭐ **New**
- **Key Files**: [genec-jdt-wrapper/src/main/java/com/genec/jdt/EclipseJDTRefactoring.java](../genec-jdt-wrapper/src/main/java/com/genec/jdt/EclipseJDTRefactoring.java)

### 6. Verification Layer (Post-Generation)

#### Syntactic Verification
- **Purpose**: Ensure generated code compiles
- **Method**: Invoke javac or Maven/Gradle
- **Key Files**: [genec/verification/syntactic_verifier.py](../genec/verification/syntactic_verifier.py)

#### Semantic Verification
- **Purpose**: Detect delegation anti-patterns
- **Checks**:
  - Single-statement methods that just delegate
  - Improved delegation detection with regex patterns ⭐ **New**
- **Key Files**: [genec/verification/semantic_verifier.py](../genec/verification/semantic_verifier.py)

#### Behavioral Verification
- **Purpose**: Ensure tests still pass
- **Method**: Run existing test suite
- **Status**: Optional (disabled by default)
- **Key Files**: [genec/verification/behavioral_verifier.py](../genec/verification/behavioral_verifier.py)

### 7. Refactoring Application Layer ⭐ **New**

#### Transactional Applicator
- **Purpose**: Apply refactorings atomically with rollback support
- **Mechanism**:
  1. Create savepoint (backup)
  2. Apply changes
  3. Verify integrity
  4. Commit or Rollback
- **Key Files**: [genec/core/transactional_applicator.py](../genec/core/transactional_applicator.py)

#### Git Integration
- **Purpose**: Manage version control operations
- **Workflow**:
  1. Create feature branch (`genec/refactor-{ClassName}`)
  2. Stage modified files
  3. Create atomic commit with detailed message
- **Key Files**: [genec/core/git_wrapper.py](../genec/core/git_wrapper.py)

#### Rollback Manager
- **Purpose**: Restore state on failure
- **Strategies**:
  - **Filesystem**: Restore from backup directory
  - **Git**: `git reset --hard` or `git revert`
- **Key Files**: [genec/core/rollback_manager.py](../genec/core/rollback_manager.py)


```
1. Input: Java class file + Git repository
          ↓
2. Parse AST → Extract dependencies → Build static graph
          ↓
3. Mine Git history → Build evolutionary graph
          ↓
4. Fuse graphs (α * static + (1-α) * evolutionary)
          ↓
5. Apply Louvain clustering → Detect communities
          ↓
6. Filter clusters → Apply size/cohesion constraints
          ↓
7. ⭐ VALIDATE CLUSTERS (Three-Tier Validation)
   a. Static validation → Auto-fix private dependencies
   b. LLM semantic validation → Override borderline cases
   c. Pattern transformation → Suggest design patterns for blocked clusters
          ↓
   ┌──────┴───────┐
   │              │
8a. Generate      8b. Generate transformation guidance
    suggestions       (pattern + structural plans)
   │
   ↓
9. Verify suggestions (syntactic, semantic, behavioral)
          ↓
10. Output: Refactoring suggestions + transformation plans
          ↓
11. ⭐ APPLY REFACTORING (Stage 7)
    a. Create Git branch
    b. Create transaction savepoint
    c. Write files (New Class + Modified Original)
    d. Verify integrity
    e. Commit transaction (Git commit) OR Rollback
```

## Configuration Architecture

GenEC uses a hierarchical YAML configuration:

```yaml
# Graph fusion weight (0.0 = only evolutionary, 1.0 = only static)
graph:
  alpha: 0.5

# Clustering constraints
clustering:
  min_methods: 2
  max_methods: 15
  min_cohesion: 0.3

# ⭐ NEW: Extraction validation
verification:
  enable_extraction_validation: true      # Tier 1: Static
  suggest_pattern_transformations: true   # Tier 3: Pattern guidance
  enable_syntactic: true                  # Post-generation
  enable_semantic: true                   # Post-generation
  enable_behavioral: false                # Optional (expensive)

# ⭐ NEW: Structural transformation
structural_transforms:
  enabled: true
  compile_check: true
  max_methods: 40
  max_fields: 20
  compile_command: ["mvn", "-q", "-DskipTests", "compile"]
  compile_timeout_seconds: 300

# LLM configuration (via AnthropicClientWrapper)
llm:
  model: claude-sonnet-4-20250514
  max_prompt_chars: 16000
  max_retries: 3
  initial_backoff: 1.0
  timeout: 60.0
```

## Output Structure

```
data/outputs/
├── {ClassName}/
│   ├── suggestion_1/
│   │   ├── new_class.java          # Generated extracted class
│   │   ├── modified_class.java     # Modified original class
│   │   └── metadata.json           # Cluster info, metrics
│   ├── suggestion_2/
│   │   └── ...
│   └── transformation_guidance/    # ⭐ NEW
│       ├── cluster_3_Strategy_Pattern.txt
│       └── cluster_5_Visitor_Pattern.txt
└── structural_plans/               # ⭐ NEW
    └── {ClassName}/
        ├── cluster_02_structural_plan.md
        └── cluster_07_structural_plan.md
```

## Extension Points

### Adding New Validation Rules

1. **Extend ExtractionValidator**:
```python
# In genec/verification/extraction_validator.py
def _check_custom_rule(self, cluster, class_deps):
    issues = []
    for method_name in cluster.get_methods():
        # Your validation logic
        if violates_rule:
            issues.append(ValidationIssue(
                severity='error',
                issue_type='custom_rule',
                description='Explanation'
            ))
    return issues
```

2. **Register in validate_extraction()**:
```python
def validate_extraction(self, cluster, class_deps):
    # ... existing validation ...
    custom_issues = self._check_custom_rule(cluster, class_deps)
    current_issues.extend(custom_issues)
```

### Adding New Design Patterns

1. **Update LLMPatternTransformer prompt**:
```python
# In genec/verification/llm_pattern_transformer.py
prompt = f"""
**For Your New Issue Type**:
   - New Pattern: Description of when to apply it
   - Code structure example
"""
```

2. **Add parsing logic** for new pattern in `_parse_transformation_response()`

### Adding New LLM Providers

1. **Create wrapper in genec/llm/**:
```python
# genec/llm/openai_client.py
class OpenAIClientWrapper:
    def send_message(self, prompt, **kwargs) -> str:
        # Implementation
```

2. **Update configuration** to support provider selection
3. **Modify consumers** to use abstract interface

## Performance Considerations

### LLM Validation Overhead

| Component | Time per Cluster | Parallelizable? | Caching? |
|-----------|-----------------|-----------------|----------|
| Static validation | ~instant | N/A | No |
| LLM semantic validation | 3-5 seconds | Yes | Future work |
| Pattern transformation | 3-5 seconds | Yes | Future work |

**Example**: For 17 clusters (AbstractFuture):
- Without LLM: ~instant
- With LLM semantic: ~51-85 seconds (3-5s × 17)
- With pattern transformation: ~102-170 seconds total

**Optimization Strategies**:
1. **Parallel LLM calls**: Process multiple clusters concurrently
2. **Caching**: Store LLM responses for identical cluster signatures
3. **Selective validation**: Only validate high-confidence clusters
4. **Batching**: Send multiple clusters in single LLM request

### Memory Usage

- Tree-sitter AST: ~O(n) where n = file size
- Dependency graphs: ~O(m²) where m = number of methods
- LLM context: Limited to 16K chars (configurable)

## Testing Strategy

### Unit Tests
- Individual validator logic
- LLM client retry behavior
- Pattern matching in transformer

### Integration Tests
- Full pipeline on known refactorings
- Validation tier interactions
- Error propagation

### Regression Tests
- 36 test cases covering edge cases
- JDT wrapper compilation checks
- Parser fallback scenarios

### Example Test Classes
- **AbstractFuture**: Complex abstract class (17 clusters, all rejected)
- **LinkedHashMultimap**: Concrete class (20 clusters, 2 valid)
- **ImmutableSetMultimap**: Immutable collection (testing edge cases)

## Security Considerations

### API Key Management
- Never commit `ANTHROPIC_API_KEY` to repository
- Use environment variables or secret management
- Graceful degradation when API unavailable

### Sandbox Execution
- JDT refactoring runs in isolated process
- Compilation validation uses read-only repository access
- No arbitrary code execution from LLM responses

### Input Validation
- Prompt truncation prevents token overflow
- Timeout enforcement prevents infinite LLM calls
- Cluster size limits prevent excessive processing

## Future Enhancements

### Planned Features
1. **Automatic Pattern Application**: Apply suggested transformations automatically
2. **Interactive Mode**: User selects patterns from suggestions
3. **Visualization**: Graph-based UI for transformation guidance
4. **Performance Optimization**: LLM response caching and parallelization
5. **Multi-Language Support**: Extend beyond Java (Python, TypeScript)

### Research Directions
1. **Learning-based Validation**: Train model on historical refactorings
2. **Cost-Benefit Analysis**: Estimate maintainability improvement vs. effort
3. **Incremental Refactoring**: Multi-step transformation plans
4. **Test Generation**: Auto-generate tests for extracted classes

## References

- Eclipse JDT Documentation: https://www.eclipse.org/jdt/
- Anthropic Claude API: https://docs.anthropic.com/
- Louvain Algorithm: Blondel et al., 2008
- RefactoringMiner: Tsantalis et al., 2018
