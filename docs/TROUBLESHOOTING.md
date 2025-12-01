# GenEC Troubleshooting Guide

This guide helps you diagnose and fix common issues when using GenEC.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Runtime Errors](#runtime-errors)
- [Eclipse JDT Issues](#eclipse-jdt-issues)
- [LLM Interface Issues](#llm-interface-issues)
- [Git Repository Issues](#git-repository-issues)
- [Verification Issues](#verification-issues)
- [Performance Issues](#performance-issues)
- [VS Code Extension Issues](#vs-code-extension-issues)

---

## Installation Issues

### Problem: `pip install` fails with dependency conflicts

**Symptoms:**
```
ERROR: Could not find a version that satisfies the requirement...
```

**Solutions:**

1. **Use a virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Update pip:**
```bash
pip install --upgrade pip
```

3. **Install dependencies individually:**
```bash
pip install pydantic>=2.0.0
pip install anthropic>=0.40.0
# ... etc
```

### Problem: `ModuleNotFoundError: No module named 'genec'`

**Solutions:**

1. **Install in development mode:**
```bash
pip install -e .
```

2. **Add to PYTHONPATH:**
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/genec"
```

---

## Configuration Issues

### Problem: `Invalid configuration` error

**Symptoms:**
```
ValueError: Invalid configuration: ...
```

**Diagnosis:**

GenEC uses Pydantic for configuration validation. Check the error message for specific validation failures.

**Common Issues:**

1. **Value out of range:**
```yaml
# WRONG
fusion:
  alpha: 1.5  # Must be 0-1

# CORRECT
fusion:
  alpha: 0.5
```

2. **Invalid enum value:**
```yaml
# WRONG
clustering:
  algorithm: invalid_algorithm

# CORRECT
clustering:
  algorithm: louvain  # Must be: louvain, leiden, or spectral
```

3. **Missing required field:**

Most fields have defaults, but check the error message if one is required.

4. **Type mismatch:**
```yaml
# WRONG
llm:
  max_tokens: "4000"  # String instead of int

# CORRECT
llm:
  max_tokens: 4000
```

**Validation Tool:**

Test your configuration:
```bash
python3 -c "from genec.config import load_config; load_config('config/config.yaml')"
```

### Problem: Config file not found

**Symptoms:**
```
WARNING: Config file not found: config/config.yaml
INFO: Using default configuration
```

**Solutions:**

1. **Specify absolute path:**
```python
pipeline = GenECPipeline('/absolute/path/to/config.yaml')
```

2. **Check working directory:**
```bash
pwd  # Should be in GenEC root
```

3. **Use defaults:**

GenEC will use sensible defaults if config file is missing.

---

## Runtime Errors

### Problem: `FileNotFoundError: Class file not found`

**Solutions:**

1. **Use absolute paths:**
```python
import os
class_file = os.path.abspath('src/MyClass.java')
```

2. **Verify file exists:**
```bash
ls -la path/to/MyClass.java
```

3. **Check file extension:**

File must be `.java`:
```python
# WRONG
pipeline.run_full_pipeline('MyClass.txt', ...)

# CORRECT
pipeline.run_full_pipeline('MyClass.java', ...)
```

### Problem: `ValueError: Class file must be a .java file`

**Solution:**

Ensure the file has `.java` extension:
```bash
mv MyClass.txt MyClass.java
```

### Problem: `PermissionError` when reading/writing files

**Solutions:**

1. **Check file permissions:**
```bash
ls -la MyClass.java
chmod 644 MyClass.java
```

2. **Check directory permissions:**
```bash
ls -ld /path/to/directory
chmod 755 /path/to/directory
```

3. **Run with appropriate user:**
```bash
sudo chown $USER:$USER MyClass.java
```

---

## Eclipse JDT Issues

### Problem: `JDT wrapper JAR not found`

**Symptoms:**
```
FileNotFoundError: Eclipse JDT wrapper JAR not found: ...
Please build it with: cd genec-jdt-wrapper && mvn package
```

**Solutions:**

1. **Build the JDT wrapper:**
```bash
cd genec-jdt-wrapper
mvn clean package
cd ..
```

2. **Verify JAR exists:**
```bash
ls -la genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar
```

3. **Update config to point to JAR:**
```yaml
code_generation:
  jdt_wrapper_jar: /absolute/path/to/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar
```

### Problem: `CodeGenerationError: Java runtime not found`

**Solutions:**

1. **Install Java 11+:**
```bash
# macOS
brew install openjdk@11

# Ubuntu/Debian
sudo apt-get install openjdk-11-jdk

# Verify
java -version
```

2. **Set JAVA_HOME:**
```bash
export JAVA_HOME=/path/to/java
export PATH=$JAVA_HOME/bin:$PATH
```

### Problem: JDT refactoring fails with `Eclipse JDT refactoring failed`

**Diagnosis:**

Check the error message for details. Common causes:

1. **Malformed Java code:**

Ensure the Java file compiles:
```bash
javac MyClass.java
```

2. **Missing dependencies:**

JDT needs to resolve types. Ensure the project compiles:
```bash
mvn compile  # or
./gradlew build
```

3. **Complex refactoring:**

Some refactorings are too complex for JDT. Try:
- Simplifying the class first
- Extracting smaller clusters
- Adjusting `max_cluster_size` in config

---

## LLM Interface Issues

### Problem: `Anthropic API key not found`

**Symptoms:**
```
WARNING: Anthropic API key not provided; LLM-based suggestions will be skipped.
```

**Solutions:**

1. **Set environment variable:**
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

2. **Add to config:**
```yaml
llm:
  api_key: your-api-key-here  # Not recommended for security
```

3. **Add to shell profile:**
```bash
# Add to ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY='your-api-key-here'
source ~/.bashrc
```

### Problem: `LLMServiceUnavailable` error

**Symptoms:**
```
LLMServiceUnavailable: Anthropic API error: ...
```

**Solutions:**

1. **Check API key:**
```bash
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","max_tokens":100,"messages":[{"role":"user","content":"test"}]}'
```

2. **Check rate limits:**

Wait a few minutes and retry.

3. **Increase timeout:**
```yaml
llm:
  timeout: 300  # Increase from default 120
```

### Problem: LLM generates invalid code

**Solutions:**

1. **Adjust temperature:**
```yaml
llm:
  temperature: 0.1  # Lower = more deterministic
```

2. **Increase max_tokens:**
```yaml
llm:
  max_tokens: 8000  # Allow longer responses
```

3. **Enable chunking:**
```yaml
chunking:
  enabled: true
```

---

## Git Repository Issues

### Problem: `InvalidGitRepositoryError`

**Symptoms:**
```
ERROR: Failed to open repository: ...
```

**Solutions:**

1. **Initialize Git repository:**
```bash
git init
git add .
git commit -m "Initial commit"
```

2. **Verify Git repository:**
```bash
git status
```

3. **Use absolute path:**
```python
repo_path = os.path.abspath('/path/to/repo')
```

### Problem: No evolutionary coupling data

**Symptoms:**
```
WARNING: No evolutionary data available
```

**Solutions:**

1. **Ensure file is tracked by Git:**
```bash
git add MyClass.java
git commit -m "Add MyClass"
```

2. **Increase history window:**
```yaml
evolution:
  window_months: 36  # Look further back
  min_commits: 1     # Lower threshold
```

3. **Check file path is relative to repo root:**

File path should be relative to repo root in Git history.

---

## Verification Issues

### Problem: `VerificationError: Compilation failed`

**Solutions:**

1. **Ensure project compiles before refactoring:**
```bash
mvn clean compile
# or
./gradlew build
```

2. **Check Java version:**
```bash
java -version  # Should match project requirements
```

3. **Disable semantic verification temporarily:**
```yaml
verification:
  enable_semantic: false  # Skip compilation check
```

### Problem: All refactorings fail verification

**Solutions:**

1. **Check prerequisites:**
```python
pipeline.check_prerequisites()
```

2. **Lower cohesion threshold:**
```yaml
clustering:
  min_cohesion: 0.3  # Lower threshold
```

3. **Increase cluster size range:**
```yaml
clustering:
  min_cluster_size: 2
  max_cluster_size: 20
```

---

## Performance Issues

### Problem: Pipeline is very slow

**Solutions:**

1. **Increase max workers:**
```yaml
verification:
  max_workers: 8  # Use more parallel workers
```

2. **Enable caching:**
```yaml
cache:
  enable: true
  directory: data/outputs/cache
```

3. **Reduce history window:**
```yaml
evolution:
  window_months: 12  # Analyze less history
```

4. **Limit suggestions:**
```python
result = pipeline.run_full_pipeline(..., max_suggestions=1)
```

### Problem: High memory usage

**Solutions:**

1. **Process smaller classes:**

Split large classes first using structural transformations.

2. **Reduce graph size:**
```yaml
fusion:
  edge_threshold: 0.2  # Remove weak edges
```

3. **Disable evolutionary mining:**
```yaml
fusion:
  alpha: 1.0  # Use only static dependencies
```

---

## VS Code Extension Issues

### Problem: Extension doesn't activate

**Solutions:**

1. **Check extension is installed:**
```bash
code --list-extensions | grep genec
```

2. **Reload VS Code:**

Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux) → "Reload Window"

3. **Check extension logs:**

View → Output → Select "GenEC" from dropdown

### Problem: `Python command not found`

**Solutions:**

1. **Configure Python path in VS Code settings:**
```json
{
  "genec.pythonPath": "/path/to/python3"
}
```

2. **Use virtual environment:**
```json
{
  "genec.pythonPath": "${workspaceFolder}/venv/bin/python"
}
```

### Problem: API key not working in extension

**Solutions:**

1. **Set in VS Code settings:**

Press `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux) → Search "GenEC API Key"

2. **Set environment variable before launching VS Code:**
```bash
export ANTHROPIC_API_KEY='your-key'
code .
```

---

## General Debugging Tips

### Enable Debug Logging

```yaml
logging:
  level: DEBUG
  file: genec_debug.log
```

Then check the log file:
```bash
tail -f genec_debug.log
```

### Use Dry Run Mode

Test without modifying files:
```yaml
refactoring_application:
  dry_run: true
```

### Check Prerequisites

```python
from genec.core.pipeline import GenECPipeline
pipeline = GenECPipeline()
status = pipeline.check_prerequisites()
for tool, available in status.items():
    print(f"{tool}: {'✓' if available else '✗'}")
```

### Validate Configuration

```bash
python3 -c "
from genec.config import load_config
try:
    config = load_config('config/config.yaml')
    print('Configuration is valid!')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

### Test Components Individually

```python
# Test dependency analysis
from genec.core.dependency_analyzer import DependencyAnalyzer
analyzer = DependencyAnalyzer()
deps = analyzer.analyze_java_class('MyClass.java', '.')
print(f"Found {len(deps.methods)} methods")

# Test LLM connection
from genec.core.llm_interface import LLMInterface
llm = LLMInterface()
print(f"LLM available: {llm.is_available()}")
```

---

## Getting Help

If you encounter an issue not covered here:

1. **Check the logs:**
   - Enable DEBUG logging
   - Look for ERROR or WARNING messages

2. **Search existing issues:**
   - GitHub Issues: https://github.com/anthropics/genec/issues

3. **Create a minimal reproduction:**
   - Smallest possible Java file that reproduces the issue
   - Full error message and stack trace
   - Configuration file (remove sensitive data)
   - GenEC version and environment info

4. **Report the issue:**
   - Include all information from step 3
   - Environment: OS, Python version, Java version
   - What you expected vs what happened

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Config file not found` | Missing config.yaml | Use default config or specify path |
| `JDT wrapper JAR not found` | JAR not built | Run `mvn package` in genec-jdt-wrapper/ |
| `Java runtime not found` | Java not installed | Install Java 11+ |
| `API key not provided` | Missing ANTHROPIC_API_KEY | Set environment variable |
| `Invalid configuration` | Bad config values | Check Pydantic validation error |
| `File not found` | Wrong file path | Use absolute path |
| `Permission denied` | Insufficient permissions | Check file/directory permissions |
| `No viable clusters found` | Class too simple | Try a larger/more complex class |
| `Compilation failed` | Project doesn't compile | Fix compilation errors first |
| `Timeout expired` | Operation took too long | Increase timeout in config |

---

For more information, see:
- [Architecture Documentation](ARCHITECTURE.md)
- [Developer Guide](DEVELOPER_GUIDE.md)
- [API Reference](API_REFERENCE.md)
