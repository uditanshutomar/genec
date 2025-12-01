# Stage 1: Dependency Analysis - Deep Analysis & Better Alternatives

## Current Implementation Overview

### Architecture
```
JavaParser (javalang + tree-sitter)
    ↓
DependencyAnalyzer
    ↓
ClassDependencies (methods, fields, matrix)
```

### What It Does
1. Parses Java class using javalang
2. Extracts methods, fields, constructors
3. Detects method calls via AST traversal
4. Detects field accesses via regex
5. Builds NxN dependency matrix

---

## Critical Flaws in Current Approach

### 🔴 FLAW 1: Parser Choice - javalang is Weak

**Current**: Uses `javalang` library
```python
tree = javalang.parse.parse(source_code)
for path, node in tree.filter(javalang.tree.MethodInvocation):
    called_methods.add(node.member)
```

**Problems**:
- ❌ **Outdated**: javalang doesn't support Java 8+ features well
- ❌ **Incomplete**: Misses lambdas, method references, streams
- ❌ **No qualifier info**: Can't distinguish `this.method()` from `other.method()`
- ❌ **No static call detection**: Misses `ClassName.staticMethod()`
- ❌ **Poor error handling**: Fails silently on modern Java

**Example failure**:
```java
// Modern Java code that javalang CANNOT parse correctly:
list.stream()
    .filter(Objects::nonNull)  // Method reference - MISSED
    .map(String::toLowerCase)   // Method reference - MISSED
    .forEach(this::process);    // Method reference - MISSED

Optional.ofNullable(value)
    .orElseGet(() -> getDefault());  // Lambda - MISSED
```

**Impact on CollectionUtils**:
- CollectionUtils uses Java 8 features (Predicates, lambdas, streams)
- Many method calls are **completely missed**
- This is why we only see 79 edges for 71 methods!

---

### 🔴 FLAW 2: Name-Based Method Matching

**Current approach** (dependency_analyzer.py:232-236):
```python
for called_method_name in class_deps.method_calls.get(method.signature, []):
    for m in all_methods:
        if m.name == called_method_name:  # WRONG!
            called_idx = method_to_idx[m.signature]
            matrix[method_idx][called_idx] = self.WEIGHT_METHOD_CALL
```

**Why this is catastrophically wrong**:

Example:
```java
class Utils {
    public static void add(String s) { }
    public static void add(int i) { }
    public static void add(String s, int i) { }

    public void caller() {
        add("test");     // Which add() is called?
        add(5);          // Which add() is called?
        add("x", 10);    // Which add() is called?
    }
}
```

Current code:
- Extracts "add" as called method
- Matches against ALL methods named "add"
- Creates **3 edges** (one to each overload)
- **All 3 are WRONG** - should be specific edges!

**Real-world impact**:
- Collections have many overloaded methods: `add`, `remove`, `get`, `contains`
- This creates **false positive edges**
- Graph becomes noisy and unreliable

---

### 🔴 FLAW 3: Regex-Based Field Detection

**Current approach** (java_parser.py:573-585):
```python
def extract_field_accesses(self, method_body: str) -> Set[str]:
    pattern = r'\b(' + '|'.join(re.escape(f) for f in field_names) + r')\b'
    matches = re.findall(pattern, method_body)
    return set(matches)
```

**Why this is terrible**:

Example:
```java
private List<String> items;

void process() {
    // All of these match "items":
    items.add("x");           // Real field access - CORRECT
    System.out.println(items); // Real field access - CORRECT
    String items = "local";    // Local variable - FALSE POSITIVE!
    /* items */               // Comment - FALSE POSITIVE!
    String s = "items";        // String literal - FALSE POSITIVE!
}
```

**Why it fails**:
- ❌ No AST context
- ❌ Can't distinguish field vs local variable
- ❌ Matches in comments and strings
- ❌ No qualifier checking (this.field vs other.field)

---

### 🔴 FLAW 4: Missing Critical Dependencies

**What's NOT detected**:

1. **Static method calls**:
```java
void methodA() {
    CollectionUtils.isEmpty(list);  // NOT DETECTED!
}
```

2. **Constructor calls**:
```java
void methodA() {
    return new ArrayList<>();  // NOT DETECTED!
}
```

3. **Lambda/method references**:
```java
void methodA() {
    list.forEach(this::process);  // NOT DETECTED!
}
```

4. **Generic type relationships**:
```java
Predicate<String> getPredicate() { ... }
void filter(Predicate<String> p) { ... }  // Related via type!
```

5. **Exception relationships**:
```java
void methodA() throws IOException { }
void methodB() throws IOException { }  // Related via exception!
```

6. **Control flow**:
```java
void methodA() {
    if (condition) methodB();
    else methodC();
    // methodB and methodC are mutually exclusive!
}
```

---

## Alternative Implementation #1: Eclipse JDT

### Why JDT is Superior

**Eclipse JDT** is what GenEC already uses for code generation! We should use it for parsing too.

**Advantages**:
✅ Full Java 21 support
✅ Complete type resolution
✅ Accurate method binding
✅ Handles generics, lambdas, method references
✅ Semantic analysis built-in
✅ Same parser for analysis + generation (consistency)

### Example Implementation

```java
// JDT-based dependency extractor
public class JDTDependencyExtractor {
    public DependencyGraph analyze(String sourceCode) {
        ASTParser parser = ASTParser.newParser(AST.JLS21);
        parser.setSource(sourceCode.toCharArray());
        parser.setKind(ASTParser.K_COMPILATION_UNIT);

        CompilationUnit cu = (CompilationUnit) parser.createAST(null);

        DependencyVisitor visitor = new DependencyVisitor();
        cu.accept(visitor);

        return visitor.getDependencyGraph();
    }
}

class DependencyVisitor extends ASTVisitor {
    private Map<IMethodBinding, Set<IMethodBinding>> methodCalls = new HashMap<>();

    @Override
    public boolean visit(MethodInvocation node) {
        IMethodBinding callerBinding = getCurrentMethod();
        IMethodBinding calleeBinding = node.resolveMethodBinding();

        if (callerBinding != null && calleeBinding != null) {
            // Exact method binding - no ambiguity!
            methodCalls.computeIfAbsent(callerBinding, k -> new HashSet<>())
                      .add(calleeBinding);
        }

        return true;
    }

    @Override
    public boolean visit(LambdaExpression node) {
        // Handle lambda expressions properly
        return true;
    }

    @Override
    public boolean visit(MethodReference node) {
        // Handle method references
        IMethodBinding binding = node.resolveMethodBinding();
        if (binding != null) {
            methodCalls.computeIfAbsent(getCurrentMethod(), k -> new HashSet<>())
                      .add(binding);
        }
        return true;
    }
}
```

**Benefits**:
- ✅ Exact method bindings (no name ambiguity)
- ✅ Handles all Java 8+ features
- ✅ Type-aware analysis
- ✅ We already have JDT wrapper!

**Implementation effort**: Medium
- Extend existing `genec-jdt-wrapper`
- Add dependency extraction methods
- Python wrapper to call Java code

---

## Alternative Implementation #2: tree-sitter (Better Usage)

### Current vs Better tree-sitter Usage

**Current**: tree-sitter is only used as fallback
```python
try:
    tree = javalang.parse.parse(wrapped)
    # ... use javalang ...
except:
    ts_methods = self._extract_method_calls_tree_sitter(method_body)
```

**Better**: Use tree-sitter as PRIMARY parser

**Why**:
✅ Fast (written in C)
✅ Error-tolerant (works on partial/broken code)
✅ Modern Java support
✅ Query language for patterns
✅ Used by GitHub, Atom, Emacs

### Example: Proper tree-sitter Queries

```python
# Define precise queries for different call types
METHOD_CALL_QUERY = """
(method_invocation
  name: (identifier) @method_name
  object: (_)? @qualifier)
"""

STATIC_CALL_QUERY = """
(method_invocation
  object: (identifier) @class_name
  name: (identifier) @method_name)
"""

METHOD_REFERENCE_QUERY = """
(method_reference
  (identifier) @method_name)
"""

class TreeSitterDependencyExtractor:
    def extract_all_calls(self, method_body: str) -> List[CallInfo]:
        tree = self.parser.parse(bytes(method_body, 'utf-8'))

        calls = []

        # Extract regular method calls
        for match in self.query_method_calls.matches(tree.root_node):
            call_info = CallInfo(
                method_name=match['method_name'].text,
                qualifier=match.get('qualifier', None),
                call_type='instance'
            )
            calls.append(call_info)

        # Extract static calls
        for match in self.query_static_calls.matches(tree.root_node):
            call_info = CallInfo(
                method_name=match['method_name'].text,
                class_name=match['class_name'].text,
                call_type='static'
            )
            calls.append(call_info)

        # Extract method references (Java 8+)
        for match in self.query_method_refs.matches(tree.root_node):
            call_info = CallInfo(
                method_name=match['method_name'].text,
                call_type='reference'
            )
            calls.append(call_info)

        return calls
```

**Benefits**:
- ✅ Distinguishes static vs instance calls
- ✅ Captures qualifiers (this.method vs other.method)
- ✅ Handles method references
- ✅ Fast and error-tolerant

**Implementation effort**: Low
- tree-sitter already available
- Just need better query patterns
- Pure Python (no Java wrapper needed)

---

## Alternative Implementation #3: Hybrid Approach (RECOMMENDED)

### Best of Both Worlds

```
Primary: tree-sitter (fast, robust)
    ↓
Enhanced: JDT for type resolution (when available)
    ↓
Result: High-quality dependency graph
```

### Architecture

```python
class HybridDependencyAnalyzer:
    def __init__(self):
        self.tree_sitter_parser = TreeSitterParser()
        self.jdt_analyzer = JDTAnalyzer()

    def analyze_class(self, class_file: str) -> ClassDependencies:
        # Phase 1: Fast structural analysis with tree-sitter
        structural_deps = self.tree_sitter_parser.extract_structure(class_file)

        # Phase 2: Enhance with JDT type resolution (if needed)
        if self.has_ambiguous_calls(structural_deps):
            type_info = self.jdt_analyzer.resolve_types(class_file)
            structural_deps = self.enhance_with_types(structural_deps, type_info)

        # Phase 3: Build enriched dependency graph
        return self.build_dependency_graph(structural_deps)

    def has_ambiguous_calls(self, deps):
        # Check if there are overloaded methods that need type resolution
        method_names = [m.name for m in deps.methods]
        return len(method_names) != len(set(method_names))
```

**Benefits**:
✅ Fast (tree-sitter primary)
✅ Accurate (JDT for disambiguation)
✅ Robust (tree-sitter error-tolerant)
✅ Type-aware (JDT semantic analysis)
✅ Leverages existing JDT wrapper

---

## Comparison Table

| Feature | Current (javalang) | tree-sitter Only | JDT Only | Hybrid (BEST) |
|---------|-------------------|------------------|----------|---------------|
| Speed | ⚡⚡ Fast | ⚡⚡⚡ Very Fast | ⚡ Slow | ⚡⚡ Fast |
| Java 8+ Support | ❌ Poor | ✅ Good | ✅ Excellent | ✅ Excellent |
| Type Resolution | ❌ None | ❌ None | ✅ Full | ✅ When needed |
| Method References | ❌ Missed | ✅ Detected | ✅ Resolved | ✅ Resolved |
| Static Calls | ❌ Missed | ✅ Detected | ✅ Resolved | ✅ Resolved |
| Overload Resolution | ❌ Wrong | ⚠️ Ambiguous | ✅ Exact | ✅ Exact |
| Error Tolerance | ❌ Brittle | ✅ Robust | ⚠️ Moderate | ✅ Robust |
| Implementation Cost | - | 🟢 Low | 🟡 Medium | 🟡 Medium |

---

## Recommended: Enhanced Dependency Types

### Beyond Method Calls

**Current**: Only 3 dependency types
```python
WEIGHT_METHOD_CALL = 1.0
WEIGHT_FIELD_ACCESS = 0.8
WEIGHT_SHARED_FIELD = 0.6
```

**Better**: Rich dependency taxonomy

```python
class DependencyType(Enum):
    # Direct dependencies (strong)
    METHOD_CALL = ("direct_call", 1.0)
    FIELD_WRITE = ("field_write", 0.95)
    FIELD_READ = ("field_read", 0.85)

    # Indirect dependencies (medium)
    SHARED_FIELD_WRITE = ("shared_field_write", 0.80)
    SHARED_FIELD_READ = ("shared_field_read", 0.70)
    SAME_EXCEPTION = ("same_exception", 0.75)
    SAME_RETURN_TYPE = ("same_return_type", 0.65)
    PARAMETER_TYPE_MATCH = ("parameter_type_match", 0.70)

    # Weak dependencies (informational)
    SAME_ANNOTATION = ("same_annotation", 0.50)
    SIMILAR_NAME = ("similar_name", 0.30)
    SEQUENTIAL_LINES = ("sequential_lines", 0.25)

    # Control flow (special)
    MUTUALLY_EXCLUSIVE = ("mutex", -0.5)  # Negative weight!

class EnrichedDependencyGraph:
    def __init__(self):
        # Multi-dimensional dependency matrix
        self.dependencies = defaultdict(lambda: defaultdict(list))

    def add_dependency(self, source: str, target: str, dep_type: DependencyType):
        self.dependencies[source][target].append(dep_type)

    def get_weight(self, source: str, target: str) -> float:
        deps = self.dependencies[source][target]
        if not deps:
            return 0.0

        # Combine multiple dependency types
        return sum(d.value[1] for d in deps) / len(deps)
```

**Example**:
```java
class Example {
    private Logger logger;  // Field

    @Deprecated
    public void oldMethod1() throws IOException {
        logger.info("Old 1");
        helper();
    }

    @Deprecated
    public void oldMethod2() throws IOException {
        logger.info("Old 2");
        helper();
    }

    private void helper() { }
}
```

**Dependencies detected**:
- `oldMethod1` → `oldMethod2`:
  - SAME_ANNOTATION (@Deprecated): 0.50
  - SAME_EXCEPTION (IOException): 0.75
  - SHARED_FIELD_READ (logger): 0.70
  - **Total: 1.95** → Strong relationship!

- `oldMethod1` → `helper`:
  - METHOD_CALL: 1.0
  - **Total: 1.0**

Current approach would miss the strong `oldMethod1`-`oldMethod2` relationship!

---

## Implementation Plan

### Phase 1: Quick Wins (1-2 days)

1. **Fix critical bugs**:
   - Use method signatures for matching (not names)
   - Add static method call detection
   - Better error logging

2. **Add diagnostics**:
```python
def _log_diagnostics(self, class_deps):
    total_methods = len(class_deps.methods)
    total_calls = sum(len(calls) for calls in class_deps.method_calls.values())

    self.logger.info(f"Dependency Analysis Results:")
    self.logger.info(f"  Methods: {total_methods}")
    self.logger.info(f"  Internal method calls: {total_calls}")
    self.logger.info(f"  Avg calls per method: {total_calls/total_methods:.2f}")
    self.logger.info(f"  Methods with no calls: {sum(1 for c in class_deps.method_calls.values() if not c)}")
    self.logger.info(f"  Dependency matrix edges: {np.count_nonzero(class_deps.dependency_matrix)}")
```

3. **Increase shared field weight**:
```python
WEIGHT_SHARED_FIELD = 0.8  # Up from 0.6
```

### Phase 2: tree-sitter Enhancement (3-5 days)

1. Make tree-sitter the primary parser
2. Add proper query patterns for:
   - Static calls
   - Method references
   - Lambda expressions
3. Keep javalang as fallback

### Phase 3: JDT Integration (1 week)

1. Extend genec-jdt-wrapper with dependency extraction
2. Add type resolution for ambiguous cases
3. Implement hybrid approach

### Phase 4: Rich Dependencies (1 week)

1. Add exception-based dependencies
2. Add type-based dependencies
3. Add annotation-based dependencies

---

## Expected Impact

### Before (Current):
```
CollectionUtils:
- 71 methods
- 79 edges (1.1 per method)
- 39 components
- Result: Unclustered
```

### After Phase 1:
```
CollectionUtils:
- 71 methods
- 150-200 edges (2-3 per method)
- 15-20 components
- Result: Some clustering possible
```

### After Phase 2:
```
CollectionUtils:
- 71 methods
- 250-300 edges (3-4 per method)
- 8-12 components
- Result: Good clustering
```

### After Phase 3+4:
```
CollectionUtils:
- 71 methods
- 400-500 edges (5-7 per method)
- 4-6 components
- Result: Excellent clustering
```

---

## Minimal Viable Fix (TODAY)

If you want to see improvement **immediately**, do this:

### 1. Fix method matching (10 minutes)

In `dependency_analyzer.py`, line 232-236:

**Before**:
```python
for called_method_name in class_deps.method_calls.get(method.signature, []):
    for m in all_methods:
        if m.name == called_method_name:
            called_idx = method_to_idx[m.signature]
            matrix[method_idx][called_idx] = self.WEIGHT_METHOD_CALL
```

**After**:
```python
for called_method_name in class_deps.method_calls.get(method.signature, []):
    # Try exact signature match first
    called_methods = [m for m in all_methods if m.signature.startswith(called_method_name + '(')]

    if not called_methods:
        # Fallback to name match
        called_methods = [m for m in all_methods if m.name == called_method_name]

    for called_method in called_methods:
        called_idx = method_to_idx[called_method.signature]
        # Weight divided by number of matches (penalize ambiguity)
        weight = self.WEIGHT_METHOD_CALL / len(called_methods)
        matrix[method_idx][called_idx] = weight
```

### 2. Add static call detection (15 minutes)

In `java_parser.py`, add this method:

```python
def _extract_static_calls(self, method_body: str, class_name: str) -> Set[str]:
    """Extract static method calls like ClassName.method()"""
    static_calls = set()

    # Pattern: ClassName.methodName(
    pattern = rf'{class_name}\.(\w+)\s*\('
    matches = re.findall(pattern, method_body)
    static_calls.update(matches)

    return static_calls
```

Then in `extract_method_calls`, add:
```python
# Add static calls
static_calls = self._extract_static_calls(method_body, class_name)
called_methods.update(static_calls)
```

### 3. Add diagnostics (5 minutes)

In `pipeline.py`, after Stage 1:

```python
# Log diagnostics
total_calls = sum(len(calls) for calls in class_deps.method_calls.values())
self.logger.info(f"Detected {total_calls} internal method calls")
self.logger.info(f"Average {total_calls/len(class_deps.methods):.1f} calls per method")
```

**Expected result**: CollectionUtils edges increase from 79 to ~150-180

---

## Conclusion

The current Stage 1 implementation has **fundamental flaws** that make effective clustering impossible:

1. ❌ Wrong parser (javalang)
2. ❌ Name-based matching
3. ❌ Missing static calls
4. ❌ Regex field detection
5. ❌ No rich dependencies

**Recommendation**:
- **Short term**: Apply minimal viable fix (30 min)
- **Medium term**: Implement tree-sitter enhancement (1 week)
- **Long term**: Full hybrid approach with rich dependencies (2-3 weeks)

This will transform GenEC from "barely works" to "production ready" for real-world refactoring!
