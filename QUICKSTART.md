# GenEC Quick Start Guide

Get up and running with GenEC in 5 minutes.

## Prerequisites

- **Python 3.10+**
- **Java 17+** (for the JDT code generation wrapper)
- **Git** (required for evolutionary coupling analysis)
- **Maven** (optional, for behavioral verification)

## Step 1: Installation (1 minute)

```bash
cd genec
pip install -e .
```

This installs all dependencies including:
- javalang, gitpython, networkx, leidenalg
- anthropic, numpy, scikit-learn
- pyyaml, python-dotenv, websockets

## Step 2: Configure API Key (30 seconds)

```bash
export ANTHROPIC_API_KEY='your-anthropic-api-key-here'
```

Get your API key from: https://console.anthropic.com/

## Step 3: Verify Installation (30 seconds)

```bash
genec --version
```

You should see `GenEC 1.0.0`.

## Step 4: Run on Example (3 minutes)

### Option A: Use Command Line (recommended)

```bash
# Basic run
genec --target path/to/YourClass.java --repo path/to/git/repo

# Preview only (no changes applied)
genec --target path/to/YourClass.java --repo path/to/git/repo --dry-run

# JSON output for tool integration
genec --target path/to/YourClass.java --repo path/to/git/repo --json

# Limit to 3 suggestions with verbose logging
genec --target path/to/YourClass.java --repo path/to/git/repo \
  --max-suggestions 3 --verbose
```

### Option B: Use Python API

```python
from genec.core.pipeline import GenECPipeline

# Initialize
pipeline = GenECPipeline('config/config.yaml')

# Run on a Java class
result = pipeline.run_full_pipeline(
    class_file='path/to/YourClass.java',
    repo_path='path/to/git/repo'
)

# View verified suggestions
for suggestion in result.verified_suggestions:
    print(f"\n{'='*60}")
    print(f"Suggested Class: {suggestion.proposed_class_name}")
    print(f"Confidence: {suggestion.confidence_score}")
    print(f"{'='*60}")
    print(f"Rationale: {suggestion.rationale}")
    if suggestion.cluster:
        print(f"\nMembers to extract:")
        for member in suggestion.cluster.member_names:
            print(f"  - {member}")
```

## What Happens?

GenEC performs 6 stages:

1. **Dependency Analysis** 
   - Parses Java AST
   - Extracts methods, fields, dependencies

2. **Evolutionary Mining** 
   - Analyzes Git commit history
   - Identifies co-changing methods

3. **Graph Building** 
   - Creates dependency graphs
   - Fuses static + evolutionary data

4. **Cluster Detection**
   - Applies Leiden algorithm
   - Identifies cohesive method groups

5. **LLM Generation** 
   - Sends clusters to Claude
   - Generates refactoring code

6. **Verification** 
   - Compiles generated code
   - Validates transformation
   - (Optional) Runs tests

## Customization

Edit `config/config.yaml` to customize:

```yaml
clustering:
  algorithm: leiden          # Community detection algorithm
  min_cluster_size: 3        # Minimum methods per cluster
  max_cluster_size: 30       # Maximum methods per cluster
  min_cohesion: 0.35         # Minimum cohesion threshold

llm:
  model: claude-sonnet-4-20250514
  max_tokens: 4000
  temperature: 0.2

verification:
  enable_syntactic: true     # Compile check
  enable_semantic: true      # Transformation check
  enable_behavioral: true    # Test suite check
```

## Understanding Output

### Metrics

**LCOM5** (Lack of Cohesion):
- 0.0 = perfect cohesion
- 1.0 = no cohesion
- Target: < 0.5

**CBO** (Coupling Between Objects):
- Lower is better
- Target: < 5

### Verification Status

-  **PASSED_ALL**: Safe to apply
-  **FAILED_SYNTACTIC**: Code doesn't compile
-  **FAILED_SEMANTIC**: Not a valid Extract Class
-  **FAILED_BEHAVIORAL**: Tests fail after refactoring

## Troubleshooting

### "No clusters detected"
- Class may already be well-designed
- Try lowering `min_cluster_size` to 2
- Check that class has >10 methods

### "ANTHROPIC_API_KEY not set"
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
```

### "Failed to parse class"
- Ensure file is valid Java
- Check file encoding (UTF-8)
- Try simplifying complex generics

### "No Git history found"
```bash
cd your/repo
git init
git add .
git commit -m "Initial commit"
```

## Next Steps

1. **Review Suggestions**: Always review generated code
2. **Run Tests**: Ensure functionality preserved
3. **Iterate**: Try different cluster sizes
4. **Evaluate**: Compare against baselines

## Learn More

- **Full Documentation**: [README.md](README.md)
- **Detailed Usage**: [USAGE.md](USAGE.md)
- **Architecture Guide**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Example Output

```
================================================================================
PIPELINE SUMMARY
================================================================================
Class: CustomerManager
Clusters detected: 5
Suggestions generated: 3
Verified suggestions: 2
Execution time: 87.34 seconds

Original Class Metrics:
  lcom5: 0.724
  tcc: 0.312
  cbo: 4.000
  num_methods: 23.000
  num_fields: 12.000
================================================================================

================================================================================
Suggestion #1: CustomerAccountManager
================================================================================

Rationale:
The account-related fields (accountBalance, accountId, creditLimit) and
methods (deposit, withdraw, getBalance) form a cohesive unit responsible
for managing customer financial transactions. Extracting this follows the
Single Responsibility Principle and improves separation of concerns.

Members to extract:
  - accountBalance (field)
  - accountId (field)
  - creditLimit (field)
  - deposit (method)
  - withdraw (method)
  - getBalance (method)

New class saved to: refactorings/CustomerAccountManager.java
Modified class saved to: refactorings/CustomerManager_modified_1.java
```

## Success!

You've successfully run GenEC! 

Now try it on your own Java classes and see what refactoring opportunities it discovers.
