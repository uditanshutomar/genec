# Tutorial 3: Working with Configuration

This tutorial demonstrates how to customize GenEC's behavior using configuration files.

## Files

- `custom_config.yaml`: Example custom configuration with detailed comments

## Key Configuration Sections

### 1. Graph Fusion (`fusion`)
- `alpha`: Weight for evolutionary coupling (0.0-1.0)
  - Higher values (0.7-0.9): Emphasize Git history
  - Lower values (0.1-0.3): Emphasize static dependencies
  - Default: 0.5 (balanced)

### 2. Clustering (`clustering`)
- `min_cluster_size`: Minimum methods per cluster
- `max_cluster_size`: Maximum methods per cluster
- `resolution`: Louvain algorithm resolution

### 3. Verification (`verification`)
- `enable_extraction_validation`: Static validation
- `suggest_pattern_transformations`: Design pattern suggestions
- `enable_semantic`: LLM semantic validation

### 4. LLM (`llm`)
- `model`: Claude model to use
- `temperature`: Creativity vs. determinism (0.0-1.0)
- `max_tokens`: Response length limit

## Running with Custom Config

```bash
python -m genec.cli \
  --target ../tutorial2/UserManager.java \
  --repo ../tutorial2 \
  --config custom_config.yaml \
  --json
```

## Configuration Validation

GenEC uses Pydantic for type-safe configuration. Invalid values are caught immediately:

```yaml
# This will fail validation:
fusion:
  alpha: 1.5  # Error: must be <= 1.0
```

Error message:
```
ValueError: Invalid configuration: fusion.alpha
  Input should be less than or equal to 1
```

## Learning Objectives

- Understand configuration parameters
- Learn when to adjust alpha (static vs. evolutionary weight)
- Use Pydantic validation to catch errors early
- Customize clustering and LLM behavior

For detailed instructions, see [TUTORIALS.md](../../docs/TUTORIALS.md#tutorial-3-working-with-configuration).
