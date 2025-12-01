# Tutorial 2: Refactoring a God Class

This tutorial demonstrates how to refactor a class with multiple responsibilities.

## Files

- `UserManager.java`: A "god class" with data access, validation, and formatting responsibilities

## Running the Tutorial

1. Initialize Git repository:
```bash
git init
git config user.email "test@example.com"
git config user.name "Test User"
git add UserManager.java
git commit -m "Initial UserManager"
```

2. Run GenEC with verbose output:
```bash
python -m genec.cli \
  --target UserManager.java \
  --repo . \
  --verbose \
  --json > results.json
```

3. View results:
```bash
cat results.json | python -m json.tool
```

## Expected Suggestions

GenEC should identify multiple extraction candidates:

1. **UserValidator**: `validateEmail()`, `validateUsername()`, `validateAge()`
2. **UserRepository**: `findById()`, `findAll()`, `save()`, `delete()`
3. **UserFormatter**: `formatUserInfo()`, `formatUserList()`

## Learning Objectives

- Understand how GenEC handles classes with multiple responsibilities
- Learn about the three-tier validation system
- See how inner classes affect extraction
- Review pattern transformation suggestions

For detailed instructions, see [TUTORIALS.md](../../docs/TUTORIALS.md#tutorial-2-refactoring-a-god-class).
