# Tutorial 1: Getting Started with GenEC

This tutorial demonstrates the basics of using GenEC to refactor a simple Java class.

## Files

- `Calculator.java`: A simple calculator with logging methods that could be extracted

## Running the Tutorial

1. Initialize Git repository:
```bash
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add Calculator.java
git commit -m "Initial commit"
```

2. Run GenEC:
```bash
python -m genec.cli \
  --target Calculator.java \
  --repo . \
  --json
```

3. Expected Result:
   - GenEC should identify the logging methods (logOperation, logTimestamp, printLog) as a candidate for extraction
   - Suggestion: Extract into a class like `OperationLogger`

## Learning Objectives

- Understand how GenEC detects cohesive method groups
- Learn to interpret JSON output
- See how Git history influences suggestions

For detailed instructions, see [TUTORIALS.md](../../docs/TUTORIALS.md#tutorial-1-getting-started).
