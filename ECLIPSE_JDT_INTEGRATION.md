# Eclipse JDT Integration Guide

This document explains the Eclipse JDT integration for GenEC's Extract Class refactoring.

## Overview

GenEC now supports **two code generation engines**:

1. **Eclipse JDT** (Recommended) - Production-quality refactoring
2. **String Manipulation** (Legacy) - Original implementation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  GenEC Python Pipeline                       │
│                                                              │
│  [Detection] → [Clustering] → [AI Naming] → [Code Gen]     │
│                                                   ↓          │
│                                    ┌──────────────┴────────┐│
│                                    │  JDT or StringManip?  ││
│                                    └──────────────┬────────┘│
└───────────────────────────────────────────────────┼─────────┘
                                                    ↓
                    ┌──────────────────────────────────────────┐
                    │    Eclipse JDT Wrapper (Java)            │
                    │                                          │
                    │  [Parse AST] → [Refactor] → [Generate]  │
                    └──────────────────────────────────────────┘
```

## What Changed

### New Files Created

**Java Infrastructure:**
- `genec-jdt-wrapper/pom.xml` - Maven project configuration
- `genec-jdt-wrapper/src/main/java/com/genec/jdt/`
  - `GenECRefactoringWrapper.java` - Main wrapper class
  - `RefactoringSpec.java` - Input specification
  - `RefactoringResult.java` - Output result
- `genec-jdt-wrapper/README.md` - Java project documentation

**Python Integration:**
- `genec/core/jdt_code_generator.py` - JDT generator class

### Modified Files

**Pipeline:**
- `genec/core/pipeline.py` - Added JDT support, dual generator system

**Configuration:**
- `config/config.yaml` - Added code_generation section

### Configuration

```yaml
code_generation:
  engine: 'eclipse_jdt'  # or 'string_manipulation'
  jdt_wrapper_jar: 'genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar'
  timeout: 60
```

## Building the JDT Wrapper

### Prerequisites
- Java 11 or higher
- Maven 3.6+

### Build Steps

```bash
# Navigate to JDT wrapper directory
cd genec-jdt-wrapper

# Build the JAR
mvn clean package

# Verify build
ls -lh target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar
```

**Output:**
- Regular JAR: `target/genec-jdt-wrapper-1.0.0.jar`
- **Fat JAR**: `target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar` (use this!)

## Usage

### Using Eclipse JDT (Recommended)

```bash
# 1. Build JDT wrapper (one-time setup)
cd genec-jdt-wrapper && mvn package && cd ..

# 2. Configure GenEC to use JDT
# Edit config/config.yaml:
#   code_generation.engine: 'eclipse_jdt'

# 3. Run GenEC normally
python3 scripts/run_pipeline.py \
  --class-file path/to/GodClass.java \
  --repo-path path/to/repo
```

### Using String Manipulation (Legacy)

```bash
# Edit config/config.yaml:
#   code_generation.engine: 'string_manipulation'

# Run GenEC
python3 scripts/run_pipeline.py \
  --class-file path/to/GodClass.java \
  --repo-path path/to/repo
```

## Testing

```bash
# Test JDT wrapper directly
cd genec-jdt-wrapper
java -jar target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar \
  --spec '{
    "projectPath": "/path/to/repo",
    "classFile": "/path/to/GodClass.java",
    "newClassName": "TestClass",
    "methods": ["method1()", "method2()"],
    "fields": ["field1"]
  }'

# Test via Python
cd ..
python3 -c "
from genec.core.jdt_code_generator import JDTCodeGenerator
gen = JDTCodeGenerator()
print('JDT Available:', gen.is_available())
"
```

## Current Behavior & Known Issues

- The JDT-powered Extract Class flow now creates the helper class, migrates the selected members, and rewrites the original methods into delegating stubs that call the helper instance.
- Constructor assignments and other direct field touches now go through generated helper accessors (`helper.getField()/setField(...)`), so the original class no longer manipulates extracted state directly.
- Extracted fields remain private inside the helper; basic getters/setters are synthesized automatically. We still owe smarter accessor synthesis for complex modifiers (e.g., immutable or computed fields).

## Development Status

### Phase 1: Infrastructure ✅ COMPLETE
- [x] Maven project structure
- [x] Eclipse JDT dependencies
- [x] Python-Java integration layer
- [x] Pipeline dual-generator support
- [x] Configuration system

### Phase 2: JDT Implementation 🚧 TODO
- [x] Eclipse workspace setup
- [x] JDT AST parsing
- [x] Extract Class refactoring execution *(methods/fields removed via ASTRewrite)*
- [ ] Type checking and validation
- [x] Actual code generation *(new helper class written to disk)*

### Phase 3: Testing & Production 📋 PLANNED
- [ ] Unit tests for wrapper
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Edge case handling

## Current Limitations

**Current behavior:**
- Extract Class runs end-to-end; helper generation plus delegation rewrites keep existing call sites compiling.
- Follow-on validation (type checking + regression suites) still relies on the verification engine.

**Next focus:**
- Harden delegation generation (encapsulation of helper state, smarter accessor synthesis).
- Implement robust validation/type checking so we fail fast if the cleaned class no longer compiles.

## Comparison: JDT vs String Manipulation

| Feature | Eclipse JDT | String Manipulation |
|---------|-------------|---------------------|
| **Code Quality** | Production-proven | Buggy (field duplication, etc.) |
| **Type Safety** | Full type checking | None |
| **Edge Cases** | Handles all Java features | Many bugs |
| **Reliability** | 15+ years battle-tested | Experimental |
| **Performance** | Slower (JVM startup) | Faster |
| **Dependencies** | Java runtime required | Python only |
| **Status** | Infrastructure ready, impl TODO | Working but buggy |

## Switching Between Engines

**To use Eclipse JDT:**
```yaml
# config/config.yaml
code_generation:
  engine: 'eclipse_jdt'
```

**To use String Manipulation:**
```yaml
# config/config.yaml
code_generation:
  engine: 'string_manipulation'
```

No code changes needed - just update config!

## Troubleshooting

### Error: "Eclipse JDT wrapper JAR not found"

```bash
# Build the JDT wrapper
cd genec-jdt-wrapper
mvn clean package
```

### Error: "Java runtime not found"

```bash
# Install Java 11+
# macOS:
brew install openjdk@11

# Ubuntu:
sudo apt-get install openjdk-11-jdk

# Verify:
java -version
```

### Error: "JDT refactoring failed"

Check if using Phase 1 (placeholder) or Phase 2 (actual implementation).
Currently in Phase 1, JDT returns placeholder code.

## Next Steps

1. **Immediate:** Test the infrastructure
   ```bash
   cd genec-jdt-wrapper && mvn package
   python3 scripts/run_pipeline.py --class-file demo/GodClass.java --repo-path demo
   ```

2. **Short-term:** Implement Phase 2 (actual JDT refactoring)
   - Set up Eclipse workspace programmatically
   - Parse Java files with JDT AST
   - Execute Extract Class refactoring
   - Return actual generated code

3. **Long-term:** Production deployment
   - Comprehensive testing
   - Performance optimization
   - Documentation
   - Release

## Benefits of JDT Integration

1. ✅ **Eliminates string manipulation bugs**
2. ✅ **Production-quality refactoring**
3. ✅ **Type-safe transformations**
4. ✅ **Handles all Java edge cases**
5. ✅ **GenEC focuses on AI + clustering (its unique value)**
6. ✅ **Eclipse team maintains refactoring engine**

## Questions?

See:
- `genec-jdt-wrapper/README.md` - Java wrapper documentation
- `genec/core/jdt_code_generator.py` - Python integration code
- Eclipse JDT docs: https://www.eclipse.org/jdt/

---

**Status:** Phase 1 Infrastructure Complete ✅ | Phase 2 Implementation TODO 🚧
