# GenEC Spoon Wrapper

This is a Java wrapper around the Spoon metaprogramming library that provides
production-grade dependency analysis for GenEC.

## What is Spoon?

Spoon is a metaprogramming library developed by INRIA (French National Research Institute)
that provides comprehensive analysis and transformation of Java source code.

- **Website**: https://spoon.gforge.inria.fr/
- **GitHub**: https://github.com/INRIA/spoon
- **License**: CeCILL-C (LGPL-compatible) / MIT
- **Java Support**: Up to Java 20+
- **Maturity**: 15+ years of development, used in research and industry

## Building

```bash
cd genec-spoon-wrapper
mvn clean package
```

This creates: `target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar`

## Usage

The JAR is called automatically by `HybridDependencyAnalyzer`. No manual invocation needed.

### Manual Testing

```bash
# Test the wrapper directly
java -jar target/genec-spoon-wrapper-1.0.0-jar-with-dependencies.jar \
  --spec '{"classFile": "/path/to/MyClass.java"}'
```

## Requirements

- Java 11+
- Maven 3.6+

## Troubleshooting

### Build Fails

If the build fails with dependency errors:

```bash
# Clear Maven cache
rm -rf ~/.m2/repository/fr/inria/gforge/spoon

# Retry build
mvn clean package
```

### Java Version

Ensure Java 11+ is installed:

```bash
java -version
# Should show: java version "11" or higher
```

On macOS:
```bash
brew install openjdk@11
```

On Ubuntu/Debian:
```bash
sudo apt install openjdk-11-jdk
```

## Architecture

```
Python (GenEC)
    ↓
SpoonParser.py
    ↓
subprocess call
    ↓
GenECSpoonWrapper.jar (this project)
    ↓
Spoon Library
    ↓
Java Source Analysis
```

## What It Analyzes

- Class structure (package, name)
- Methods (signatures, modifiers, parameters, body)
- Constructors (signatures, modifiers, parameters, body)
- Fields (names, types, modifiers)
- Method calls (which methods call which)
- Field accesses (which methods access which fields)
- Constructor chaining (this/super calls)

## Output Format

JSON with this structure:

```json
{
  "success": true,
  "className": "MyClass",
  "packageName": "com.example",
  "methods": [
    {
      "name": "myMethod",
      "signature": "myMethod(String)",
      "returnType": "void",
      "modifiers": ["public"],
      "parameters": [{"name": "arg", "type": "String"}],
      "startLine": 10,
      "endLine": 15,
      "body": "..."
    }
  ],
  "constructors": [...],
  "fields": [...],
  "methodCalls": {
    "myMethod(String)": ["helperMethod", "anotherMethod"]
  },
  "fieldAccesses": {
    "myMethod(String)": ["myField", "count"]
  }
}
```

## License

Same as GenEC project.
