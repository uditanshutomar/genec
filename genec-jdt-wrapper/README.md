# GenEC Eclipse JDT Wrapper

Eclipse JDT-based refactoring engine for GenEC Extract Class refactoring.

## Overview

This Java project provides a production-quality code generation engine for GenEC using Eclipse JDT (Java Development Tools). Instead of string manipulation, it leverages Eclipse's battle-tested refactoring infrastructure used by millions of developers.

## Architecture

```
GenEC (Python)                    JDT Wrapper (Java)
    ↓                                    ↓
Clustering + AI Naming  →  Eclipse JDT Refactoring
    ↓                                    ↓
Verification          ←   Type-safe Java Code
```

## Building

### Prerequisites
- Java 11 or higher
- Maven 3.6+

### Build Command

```bash
cd genec-jdt-wrapper
mvn clean package
```

This creates:
- `target/genec-jdt-wrapper-1.0.0.jar` - Regular JAR
- `target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar` - Fat JAR (use this!)

## Usage

### From Command Line

```bash
java -jar target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar \
  --spec '{
    "projectPath": "/path/to/project",
    "classFile": "/path/to/GodClass.java",
    "newClassName": "AccountManager",
    "methods": ["deposit(double)", "withdraw(double)"],
    "fields": ["accountBalance", "accountNumber"]
  }'
```

### From Python (via GenEC)

```python
from genec.core.jdt_code_generator import JDTCodeGenerator

generator = JDTCodeGenerator()
result = generator.generate(
    cluster=cluster,
    new_class_name="AccountManager",
    class_file="path/to/GodClass.java",
    repo_path="path/to/repo",
    class_deps=class_deps
)

print(result.new_class_code)
print(result.modified_original_code)
```

## Input Specification

JSON format expected by `--spec` parameter:

```json
{
  "projectPath": "/absolute/path/to/repository",
  "classFile": "/absolute/path/to/JavaClass.java",
  "newClassName": "ExtractedClassName",
  "methods": [
    "methodSignature1(Type)",
    "methodSignature2(Type,Type)"
  ],
  "fields": [
    "fieldName1",
    "fieldName2"
  ]
}
```

## Output Format

JSON format returned on stdout:

```json
{
  "success": true,
  "message": "Refactoring completed successfully",
  "newClassCode": "package ...\npublic class ExtractedClassName { ... }",
  "modifiedOriginalCode": "package ...\npublic class OriginalClass { ... }",
  "newClassPath": "/path/to/ExtractedClassName.java"
}
```

## Error Handling

On error, returns JSON on stderr with exit code 1:

```json
{
  "success": false,
  "message": "Error description..."
}
```

## Development Status

### Phase 1: Infrastructure (COMPLETE) ✅
- [x] Maven project setup
- [x] Eclipse JDT dependencies
- [x] JSON input/output handling
- [x] Python integration layer
- [x] Placeholder refactoring logic

### Phase 2: JDT Implementation (TODO)
- [ ] Eclipse workspace setup
- [ ] JDT AST parsing
- [ ] Extract Class refactoring execution
- [ ] Type checking and validation
- [ ] Actual code generation

### Phase 3: Testing & Refinement (TODO)
- [ ] Unit tests for wrapper
- [ ] Integration tests with GenEC
- [ ] Edge case handling
- [ ] Performance optimization

## Dependencies

- Eclipse JDT Core 3.37.0
- Eclipse Platform Runtime 3.29.0
- Eclipse LTK (Refactoring) 3.14.0
- Gson 2.10.1 (JSON processing)

## License

Same as GenEC project.

## Contributing

This is part of the GenEC project. Contributions welcome!
