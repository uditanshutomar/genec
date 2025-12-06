# Developer Guide

## Getting Started

### Prerequisites
- Python 3.8+
- Java JDK 11+ (for JDT wrapper)
- Maven 3.6+ (for building JDT wrapper)
- Anthropic API key (for LLM features)

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd genec

# Install in development mode
pip install -e .

# Build JDT wrapper
cd genec-jdt-wrapper
mvn clean package
cd ..

# Set up API key
export ANTHROPIC_API_KEY='your-key-here'

# Run tests
pytest tests/ -v
```

## Project Structure

```
genec/
├── genec/
├── genec/                      # Main package
│   ├── core/                   # Core pipeline components
│   │   ├── stages/             # Pipeline stages
│   │   └── pipeline_runner.py  # Pipeline orchestrator
│   ├── llm/                    # LLM client abstractions
│   ├── parsers/                # Language parsers
│   ├── metrics/                # Code quality metrics
│   ├── verification/           # Validation layers
│   └── structural/             # Structural transformation
├── genec-jdt-wrapper/          # Java code generation
├── tests/                      # Test suite
├── scripts/                    # CLI scripts
├── config/                     # Configuration files
└── docs/                       # Documentation
```

## Extending the Validation System

### Adding a New Static Validation Rule

**Use Case**: You want to detect a new blocking pattern (e.g., synchronized methods)

**Steps**:

1. **Define the validation logic** in `genec/verification/extraction_validator.py`:

```python
def _check_synchronized_methods(
    self,
    cluster: Cluster,
    class_deps: ClassDependencies
) -> List[ValidationIssue]:
    """Check if cluster contains synchronized methods."""
    issues = []
    method_names = cluster.get_methods()

    for method_name in method_names:
        method_info = class_deps.methods.get(method_name)
        if not method_info:
            continue

        # Check if method is synchronized
        modifiers = method_info.get('modifiers', [])
        if 'synchronized' in modifiers:
            issues.append(ValidationIssue(
                severity='warning',  # or 'error' if blocking
                issue_type='synchronized_method',
                description=f"Method '{method_name}' is synchronized - "
                           f"may cause concurrency issues in extracted class"
            ))

    return issues
```

2. **Register the check** in `validate_extraction()`:

```python
def validate_extraction(
    self,
    cluster: Cluster,
    class_deps: ClassDependencies
) -> Tuple[bool, List[ValidationIssue]]:
    # ... existing validation logic ...

    # Add your new check
    sync_issues = self._check_synchronized_methods(cluster, class_deps)
    current_issues.extend(sync_issues)

    # ... rest of validation ...
```

3. **Add tests** in `tests/test_extraction_validator.py`:

```python
def test_synchronized_method_detection():
    """Test detection of synchronized methods."""
    cluster = create_test_cluster(['synchronizedMethod', 'regularMethod'])
    class_deps = create_test_class_deps()

    # Mark method as synchronized
    class_deps.methods['synchronizedMethod']['modifiers'] = ['public', 'synchronized']

    validator = ExtractionValidator()
    is_valid, issues = validator.validate_extraction(cluster, class_deps)

    # Should have warning about synchronized method
    sync_issues = [i for i in issues if i.issue_type == 'synchronized_method']
    assert len(sync_issues) == 1
    assert 'synchronized' in sync_issues[0].description.lower()
```

### Adding a New Design Pattern Suggestion

**Use Case**: You want to suggest the Factory pattern for certain cases

**Steps**:

1. **Update the LLM prompt** in `genec/verification/llm_pattern_transformer.py`:

```python
def suggest_transformation(
    self,
    cluster: Cluster,
    class_deps: ClassDependencies,
    blocking_issues: List[str]
) -> Optional[TransformationStrategy]:

    prompt = f"""You are a Java refactoring expert...

**For Constructor Dependencies**:
   - Factory Pattern: Encapsulate object creation logic
   - Builder Pattern: Construct complex objects step by step
   - Prototype Pattern: Clone existing instances

**For Abstract Method Dependencies**:
   - Strategy Pattern: Pass behavior as parameters
   ...

    # ... rest of prompt ...
    """
```

2. **Enhance response parsing** (if needed):

```python
def _parse_transformation_response(self, response_text: str) -> Optional[TransformationStrategy]:
    # ... existing parsing ...

    # Add specific handling for Factory pattern if needed
    if 'factory' in pattern_name.lower():
        # Extract factory-specific details
        pass

    return strategy
```

3. **Test the pattern** with real code:

```python
def test_factory_pattern_suggestion():
    """Test Factory pattern suggestion for constructor complexity."""
    cluster = create_cluster_with_constructor_deps()
    class_deps = create_test_class_deps()
    blocking_issues = ["Constructor requires 5 parameters with complex initialization"]

    transformer = LLMPatternTransformer()
    strategy = transformer.suggest_transformation(cluster, class_deps, blocking_issues)

    assert strategy is not None
    assert 'factory' in strategy.pattern_name.lower()
    assert strategy.confidence >= 0.6
```

### Creating a Custom Validation Tier

**Use Case**: You want to add a custom validation layer between static and LLM

**Steps**:

1. **Create new validator** in `genec/verification/custom_validator.py`:

```python
from typing import Tuple, List
from dataclasses import dataclass

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.verification.extraction_validator import ValidationIssue

@dataclass
class CustomValidationResult:
    """Result of custom validation."""
    is_valid: bool
    confidence: float
    issues: List[ValidationIssue]
    reasoning: str

class CustomValidator:
    """Custom validation logic."""

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    def validate(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies,
        static_issues: List[ValidationIssue]
    ) -> CustomValidationResult:
        """
        Perform custom validation.

        Args:
            cluster: The cluster to validate
            class_deps: Class dependency information
            static_issues: Issues found by static validator

        Returns:
            CustomValidationResult with validation decision
        """
        # Your custom logic here
        # Example: Check code complexity metrics

        complexity_score = self._calculate_complexity(cluster, class_deps)

        if complexity_score > 10:
            return CustomValidationResult(
                is_valid=False,
                confidence=0.9,
                issues=[ValidationIssue(
                    severity='error',
                    issue_type='high_complexity',
                    description=f'Cluster complexity score {complexity_score} too high'
                )],
                reasoning='Cluster is too complex to extract safely'
            )

        return CustomValidationResult(
            is_valid=True,
            confidence=0.8,
            issues=[],
            reasoning='Complexity acceptable for extraction'
        )

    def _calculate_complexity(self, cluster, class_deps) -> float:
        # Your complexity calculation
        return 5.0
```

2. **Integrate into ExtractionValidator**:

```python
# In genec/verification/extraction_validator.py

class ExtractionValidator:
    def __init__(self, auto_fix: bool = True, use_llm: bool = True,
                 use_custom: bool = True):
        # ... existing init ...

        # Initialize custom validator
        if use_custom:
            from genec.verification.custom_validator import CustomValidator
            self.custom_validator = CustomValidator()
        else:
            self.custom_validator = None

    def validate_extraction(self, cluster, class_deps):
        # ... existing static validation ...

        # If static validation failed, try custom validator first
        if not is_valid and self.custom_validator:
            custom_result = self.custom_validator.validate(
                cluster, class_deps, current_issues
            )

            if custom_result.is_valid and custom_result.confidence >= 0.8:
                self.logger.info(
                    f"Custom validator overrode static rejection: {custom_result.reasoning}"
                )
                is_valid = True
                # Optionally clear or modify issues

        # ... continue with LLM validation if needed ...
```

3. **Configure** in `config/config.yaml`:

```yaml
verification:
  enable_extraction_validation: true
  use_custom_validator: true
  custom_complexity_threshold: 10
```

## Working with the LLM Client

### Basic Usage

```python
from genec.llm import AnthropicClientWrapper, LLMConfig

# Create client with custom configuration
config = LLMConfig(
    model="claude-sonnet-4-20250514",
    max_retries=5,
    initial_backoff=2.0,
    timeout=120.0
)

llm = AnthropicClientWrapper(config=config)

# Send message
try:
    response = llm.send_message(
        prompt="Your prompt here",
        max_tokens=3000,
        temperature=0.3
    )
    print(response)
except LLMServiceUnavailable as e:
    print(f"LLM service not available: {e}")
except LLMRequestFailed as e:
    print(f"LLM request failed: {e}")
```

### Adding a New LLM Provider

**Steps**:

1. **Create provider wrapper** in `genec/llm/openai_client.py`:

```python
from typing import Optional
import openai
from genec.llm.anthropic_client import LLMConfig, LLMServiceUnavailable, LLMRequestFailed

class OpenAIClientWrapper:
    """OpenAI client with consistent interface."""

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.config = config or LLMConfig()

        if not self.api_key:
            self._enabled = False
        else:
            self._enabled = True
            openai.api_key = self.api_key

    @property
    def enabled(self) -> bool:
        return self._enabled

    def send_message(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.2
    ) -> str:
        """Send message to OpenAI with retry logic."""
        if not self.enabled:
            raise LLMServiceUnavailable("OpenAI client disabled")

        # Implement retry logic similar to AnthropicClientWrapper
        # ...

        try:
            response = openai.ChatCompletion.create(
                model=model or self.config.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            raise LLMRequestFailed(f"OpenAI request failed: {e}")
```

2. **Update validators** to support provider selection:

```python
# In genec/verification/llm_semantic_validator.py

class LLMSemanticValidator:
    def __init__(self, provider: str = "anthropic", api_key: str = None):
        if provider == "anthropic":
            from genec.llm import AnthropicClientWrapper
            self.llm = AnthropicClientWrapper(api_key=api_key)
        elif provider == "openai":
            from genec.llm.openai_client import OpenAIClientWrapper
            self.llm = OpenAIClientWrapper(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

3. **Add configuration**:

```yaml
llm:
  provider: anthropic  # or openai
  anthropic_model: claude-sonnet-4-20250514
  openai_model: gpt-4-turbo
```

## Testing Guidelines

### Unit Tests

Test individual components in isolation:

```python
# tests/test_extraction_validator.py

def test_abstract_method_detection():
    """Test that abstract method calls are detected."""
    # Create test cluster
    cluster = Cluster(
        id=1,
        member_names=['method1', 'method2'],
        internal_cohesion=0.8,
        external_coupling=0.2
    )

    # Create test class dependencies
    class_deps = ClassDependencies(
        class_name='TestClass',
        methods={
            'method1': {
                'calls': ['abstractMethod'],
                'modifiers': ['public']
            },
            'method2': {
                'calls': [],
                'modifiers': ['public']
            }
        },
        fields={},
        abstract_methods=['abstractMethod'],
        inner_classes=[]
    )

    # Validate
    validator = ExtractionValidator(auto_fix=False, use_llm=False)
    is_valid, issues = validator.validate_extraction(cluster, class_deps)

    # Assert
    assert not is_valid
    assert any(i.issue_type == 'abstract_method_call' for i in issues)
```

### Integration Tests

Test full pipeline flows:

```python
# tests/integration/test_validation_pipeline.py

def test_full_validation_flow():
    """Test complete validation pipeline."""
    pipeline = GenECPipeline('config/config.yaml')

    result = pipeline.run_full_pipeline(
        class_file='tests/fixtures/ComplexClass.java',
        repo_path='tests/fixtures/test_repo'
    )

    # Check that validation occurred
    assert hasattr(result, 'all_clusters')
    assert hasattr(result, 'filtered_clusters')

    # Rejected clusters should have rejection_issues
    rejected = [c for c in result.all_clusters
                if hasattr(c, 'rejection_issues') and c.rejection_issues]

    for cluster in rejected:
        assert len(cluster.rejection_issues) > 0
```

### Mock LLM Responses

For testing LLM-dependent code without API calls:

```python
from unittest.mock import Mock, patch

def test_llm_semantic_validation_with_mock():
    """Test LLM validation with mocked response."""

    # Mock the LLM client
    mock_llm = Mock()
    mock_llm.enabled = True
    mock_llm.send_message.return_value = """
    SAFE_TO_EXTRACT: false
    CONFIDENCE: 0.85
    REASONING: Abstract method calls cannot be resolved without delegation pattern
    """

    # Create validator with mocked client
    validator = LLMSemanticValidator()
    validator.llm = mock_llm

    # Test validation
    cluster = create_test_cluster()
    class_deps = create_test_class_deps()
    issues = [create_test_issue()]

    result = validator.validate_extraction_semantics(cluster, class_deps, issues)

    # Assertions
    assert not result.is_valid
    assert result.confidence == 0.85
    assert 'delegation pattern' in result.reasoning.lower()

    # Verify LLM was called correctly
    mock_llm.send_message.assert_called_once()
```

## Debugging Tips

### Enable Verbose Logging

```python
# In your script or test
import logging
logging.basicConfig(level=logging.DEBUG)

# Or via config
logging:
  level: DEBUG
```

### Inspect LLM Prompts

```python
# Add to LLM client for debugging
class AnthropicClientWrapper:
    def send_message(self, prompt, **kwargs):
        # Log prompt before sending
        self.logger.debug(f"LLM Prompt:\n{prompt}")

        response = # ... actual call ...

        # Log response
        self.logger.debug(f"LLM Response:\n{response}")

        return response
```

### View Cluster Details

```python
# In pipeline.py, add debugging
for cluster in all_clusters:
    self.logger.debug(f"Cluster {cluster.id}:")
    self.logger.debug(f"  Methods: {cluster.get_methods()}")
    self.logger.debug(f"  Fields: {cluster.get_fields()}")
    if hasattr(cluster, 'rejection_issues'):
        self.logger.debug(f"  Rejection issues: {cluster.rejection_issues}")
```

## Performance Optimization

### Parallel LLM Validation

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def validate_clusters_parallel(clusters, class_deps, max_workers=5):
    """Validate multiple clusters in parallel."""
    validator = LLMSemanticValidator()
    results = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all validation tasks
        future_to_cluster = {
            executor.submit(
                validator.validate_extraction_semantics,
                cluster, class_deps, cluster.rejection_issues
            ): cluster
            for cluster in clusters
            if hasattr(cluster, 'rejection_issues')
        }

        # Collect results as they complete
        for future in as_completed(future_to_cluster):
            cluster = future_to_cluster[future]
            try:
                result = future.result()
                results[cluster.id] = result
            except Exception as e:
                logger.error(f"Validation failed for cluster {cluster.id}: {e}")

    return results
```

### Caching LLM Responses

```python
import hashlib
import json
from pathlib import Path

class CachedLLMValidator:
    """LLM validator with response caching."""

    def __init__(self, cache_dir: Path = Path('data/cache/llm')):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.validator = LLMSemanticValidator()

    def _get_cache_key(self, cluster, class_deps, issues):
        """Generate unique cache key for cluster + issues."""
        data = {
            'methods': sorted(cluster.get_methods()),
            'fields': sorted(cluster.get_fields()),
            'issues': sorted([i.description for i in issues])
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def validate_with_cache(self, cluster, class_deps, issues):
        """Validate with caching."""
        cache_key = self._get_cache_key(cluster, class_deps, issues)
        cache_file = self.cache_dir / f"{cache_key}.json"

        # Check cache
        if cache_file.exists():
            with open(cache_file, 'r') as f:
                cached = json.load(f)
                return SemanticValidationResult(**cached)

        # Call LLM
        result = self.validator.validate_extraction_semantics(
            cluster, class_deps, issues
        )

        # Store in cache
        with open(cache_file, 'w') as f:
            json.dump({
                'is_valid': result.is_valid,
                'confidence': result.confidence,
                'reasoning': result.reasoning
            }, f)

        return result
```

## Contributing

### Pull Request Process

1. **Create feature branch**: `git checkout -b feature/your-feature`
2. **Write tests**: Ensure >80% coverage for new code
3. **Update documentation**: Add to relevant `.md` files
4. **Run full test suite**: `pytest tests/ -v`
5. **Commit with conventional commits**: `feat:`, `fix:`, `docs:`, etc.
6. **Create PR** to `main` branch with description

### Code Style

- Follow PEP 8 for Python code
- Use type hints for all function signatures
- Add docstrings to all public methods
- Keep functions under 50 lines when possible
- Use meaningful variable names

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`

**Example**:
```
feat(validation): add synchronized method detection

Add check for synchronized methods in ExtractionValidator to warn
about potential concurrency issues in extracted classes.

- Add _check_synchronized_methods() method
- Register check in validate_extraction()
- Add tests for synchronized method detection

Testing: 36 regression tests passed
```

## Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [Eclipse JDT Guide](https://www.eclipse.org/jdt/ui/index.php)
- [Anthropic API Docs](https://docs.anthropic.com/)
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Conventional Commits](https://www.conventionalcommits.org/)
