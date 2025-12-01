# GenEC Examples and Tutorials

This directory contains hands-on tutorials and examples for learning GenEC.

## Tutorials

### [Tutorial 1: Getting Started](tutorial1/)
**Level**: Beginner
**Time**: 10-15 minutes
**Objective**: Learn the basics of GenEC by refactoring a simple Calculator class.

**Key Concepts**:
- Running GenEC CLI
- Understanding JSON output
- Identifying cohesive method groups
- Basic dependency analysis

### [Tutorial 2: Refactoring a God Class](tutorial2/)
**Level**: Intermediate
**Time**: 20-30 minutes
**Objective**: Refactor a class with multiple responsibilities (UserManager).

**Key Concepts**:
- God class anti-pattern
- Three-tier validation system
- Multiple extraction opportunities
- Inner classes and their impact

### [Tutorial 3: Working with Configuration](tutorial3/)
**Level**: Intermediate
**Time**: 15-20 minutes
**Objective**: Customize GenEC's behavior using configuration files.

**Key Concepts**:
- Pydantic configuration system
- Alpha parameter (static vs. evolutionary weight)
- Clustering parameters
- LLM model selection and temperature

### [Tutorial 4: Understanding Validation Results](tutorial4/)
**Level**: Advanced
**Time**: 20-25 minutes
**Objective**: Learn to interpret GenEC's three-tier validation system.

**Key Concepts**:
- Static validation (abstract methods, inner classes)
- LLM semantic validation (confidence scores)
- Pattern transformation suggestions
- Structural scaffolding plans

### [Tutorial 5: Advanced - Multi-file Projects](tutorial5/)
**Level**: Advanced
**Time**: 30-40 minutes
**Objective**: Use GenEC on a realistic multi-class Java project.

**Key Concepts**:
- Real-world project structure
- Iterative refactoring with `--apply-all`
- Automatic backup management
- Compilation verification
- Git history integration

## Quick Start

To get started with the tutorials:

1. **Install GenEC**:
   ```bash
   cd ../../  # Go to GenEC root
   pip install -e .
   ```

2. **Set API Key**:
   ```bash
   export ANTHROPIC_API_KEY='your-api-key-here'
   ```

3. **Choose a Tutorial**:
   ```bash
   cd examples/tutorial1
   cat README.md
   ```

4. **Follow the Instructions**:
   Each tutorial has a README.md with step-by-step instructions.

## Tutorial Progression

We recommend following the tutorials in order:

```
Tutorial 1 (Beginner)
    ↓
Tutorial 2 (Intermediate) ← Tutorial 3 (Intermediate)
    ↓                              ↓
Tutorial 4 (Advanced)
    ↓
Tutorial 5 (Advanced)
```

- **Beginners**: Start with Tutorial 1
- **Experienced with refactoring**: Start with Tutorial 2
- **Want to customize behavior**: Jump to Tutorial 3
- **Need deep understanding**: Proceed to Tutorial 4 and 5

## Additional Resources

- **Full Tutorial Guide**: [docs/TUTORIALS.md](../docs/TUTORIALS.md)
- **API Reference**: [docs/API_REFERENCE.md](../docs/API_REFERENCE.md)
- **Architecture**: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)

## Example Code

Each tutorial includes:
- ✓ Complete Java source files
- ✓ Step-by-step README
- ✓ Configuration examples (where applicable)
- ✓ Expected output examples

## Getting Help

If you encounter issues:

1. Check the tutorial README.md
2. Review [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
3. Open an issue: https://github.com/YOUR_USERNAME/genec/issues

## Contributing Examples

Have a great example? We'd love to include it! See [DEVELOPER_GUIDE.md](../docs/DEVELOPER_GUIDE.md) for contribution guidelines.
