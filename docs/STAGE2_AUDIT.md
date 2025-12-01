# Stage 2: Evolutionary Coupling Mining - Comprehensive Audit

## Overview
Stage 2 mines evolutionary coupling from Git commit history to identify methods that frequently change together. This complements static dependency analysis with temporal collaboration patterns.

## Files Involved
1. `genec/core/evolutionary_miner.py` (403 lines)
2. `genec/core/graph_builder.py` (318 lines)
3. `genec/core/pipeline.py` (_stage2_mine_evolutionary and _stage3_build_graphs methods)

---

## Critical Issues Found

### 🔴 ISSUE 1: Name-Only Method Matching
**Location**: `evolutionary_miner.py:244-258` and `graph_builder.py:95-110`

**Problem**:
```python
# evolutionary_miner.py line 251
for path, node in tree.filter(javalang.tree.MethodDeclaration):
    methods.append(node.name)  # Only stores NAME, not signature
```

**Why it's critical**:
- Method names extracted from Git history are **simple names only** (e.g., "add")
- When mapping to static graph, uses name-to-signature dictionary: `{m.name: m.signature for m in methods}`
- **Fails for overloaded methods**: Multiple methods with same name → only last one kept in dict
- Example collision:
  ```java
  public void add(String s)         // name: "add"
  public void add(int i, String s)  // name: "add" (OVERWRITES!)
  ```

**Impact on CollectionUtils**:
- With 71 methods, likely has overloaded methods (add, get, remove, etc.)
- Evolutionary coupling detected for "add" maps to arbitrary signature
- **Wrong edges** created in evolutionary graph
- Fusion produces **incorrect coupling** between methods

**Fix Required**:
```python
# Need to extract signatures from Git history, not just names
def _extract_methods_from_content(self, content: str) -> List[str]:
    methods = []
    try:
        tree = self.parser.parse_file_content(content)
        if tree:
            for path, node in tree.filter(javalang.tree.MethodDeclaration):
                # Extract full signature, not just name
                params = ', '.join(p.type.name for p in node.parameters) if node.parameters else ''
                signature = f"{node.name}({params})"
                methods.append(signature)
    return methods
```

---

### 🔴 ISSUE 2: Regex-Based Method Extraction
**Location**: `evolutionary_miner.py:260-281`

**Problem**:
```python
# Fallback method extraction using regex
method_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{'
```

**Weaknesses**:
1. **Doesn't capture parameter types** - loses overload information
2. **Fails on Java 8+ features**: lambdas, default methods, method references
3. **Misses annotations** that might be on separate lines
4. **False positives** on method calls that span multiple lines
5. **Fragile** to formatting variations

**Example failure**:
```java
@Override
@Deprecated
public static <T> List<T>
    complexMethod(
        Map<String, List<T>> param1,
        Predicate<T> param2
    ) {
```
Regex won't match this due to multi-line formatting.

**Impact**:
- Method detection inconsistent across commits
- Missed methods = underestimated evolutionary coupling
- False positives = wrong coupling edges

---

### 🔴 ISSUE 3: Brace Counting for Method Boundaries
**Location**: `evolutionary_miner.py:283-299`

**Problem**:
```python
def _find_method_end(self, lines: List[str], start_idx: int) -> int:
    brace_count = 0
    for i in range(start_idx, len(lines)):
        for char in line:
            if char == '{':
                brace_count += 1
```

**Fatal flaws**:
1. **Doesn't handle strings**: `String s = "function() { code }";` → breaks counting
2. **Doesn't handle comments**: `// This { is just a comment` → counted as brace
3. **Doesn't handle char literals**: `char c = '{';` → counted
4. **Nested classes** confuse the counting

**Example failure**:
```java
public void methodA() {
    String code = "if (x) { doSomething(); }";  // 2 braces in string!
    if (condition) {
        // Real code
    }
}  // Brace count wrong, method end incorrectly detected
```

**Impact**:
- Methods assigned wrong line ranges
- Changed lines mapped to wrong methods
- **Phantom coupling** between unrelated methods
- **Missed coupling** for actual co-changes

---

### 🟡 ISSUE 4: No Handling for Merge Commits
**Location**: `evolutionary_miner.py:160-222`

**Problem**:
```python
if not commit.parents:
    # Initial commit
    ...
parent = commit.parents[0]  # Always uses first parent
```

**Issue**:
- Merge commits have **multiple parents** (2+)
- Code only analyzes diff against **first parent**
- Misses changes from **second parent** (merged branch)

**Impact on real repos**:
- Apache Commons uses feature branches extensively
- Merge commits combine changes from multiple developers
- **Underestimates coupling** by missing merged changes

**Expected behavior**:
```python
if len(commit.parents) > 1:
    # Merge commit - check all parents or skip
    # Option 1: Skip merge commits (conservative)
    return set()
    # Option 2: Union changes from all parents
    all_changed = set()
    for parent in commit.parents:
        all_changed.update(self._diff_against_parent(commit, parent, file_path))
    return all_changed
```

---

### 🟡 ISSUE 5: Inefficient Diff Processing
**Location**: `evolutionary_miner.py:198-214`

**Problem**:
```python
# Get diff
diff = repo.git.diff(parent.hexsha, commit.hexsha, file_path, unified=0)

# Extract changed line ranges
changed_lines = self._extract_changed_lines(diff)

# Get methods in both versions
old_methods = self._extract_methods_with_lines(old_content)
new_methods = self._extract_methods_with_lines(new_content)

# Check which methods overlap with changed lines
for method, (start, end) in new_methods.items():
    for changed_start, changed_end in changed_lines:
        if not (end < changed_start or start > changed_end):
```

**Inefficiencies**:
1. **Parses entire file content** for every commit (expensive)
2. **Regex runs on full source** each time
3. **O(n*m) overlap checking** (methods × changed ranges)
4. **No caching** of method ranges across commits

**Performance impact**:
- For 71 methods, 50 commits: 3,550 method extractions
- CollectionUtils is ~3000 lines: regex over 150,000 lines total
- Should cache method ranges per file version

---

### 🟡 ISSUE 6: Weak Coupling Formula
**Location**: `evolutionary_miner.py:301-314`

**Current formula**:
```python
coupling(m1, m2) = commits_both / sqrt(commits_m1 * commits_m2)
```

**Problems**:
1. **Penalizes frequently changed methods**
   - If m1 changes 100 times, m2 changes 5 times, both change together 4 times:
   - Coupling = 4 / sqrt(100 * 5) = 4 / 22.36 = 0.18
   - But 80% of m2's changes involve m1 (strong coupling!)

2. **No time decay**
   - Co-changes from 3 years ago weighted same as yesterday
   - Recent coupling more relevant for refactoring

3. **No statistical significance test**
   - Is 3 co-changes significant or random?
   - No confidence interval

**Better alternatives**:

**Jaccard Index** (symmetric):
```python
coupling = commits_both / (commits_m1 + commits_m2 - commits_both)
# Example: 4 / (100 + 5 - 4) = 4 / 101 = 0.04 (still low)
```

**Asymmetric Support**:
```python
support_m1_to_m2 = commits_both / commits_m1  # 4/100 = 0.04
support_m2_to_m1 = commits_both / commits_m2  # 4/5 = 0.80 (strong!)
coupling = max(support_m1_to_m2, support_m2_to_m1)  # Use maximum
```

**Time-weighted**:
```python
# Weight recent commits higher
for commit in commits:
    age_days = (now - commit.date).days
    weight = exp(-age_days / 180)  # Decay over 6 months
    cochange_count += weight
```

---

### 🟢 ISSUE 7: Missing javalang Import
**Location**: `evolutionary_miner.py:251`

**Problem**:
```python
for path, node in tree.filter(javalang.tree.MethodDeclaration):
    methods.append(node.name)
```

But at top of file:
```python
from genec.parsers.java_parser import JavaParser
```

**No `import javalang`!**

**Why it works anyway**:
- JavaParser imports javalang internally
- Code relies on transitive import (fragile)
- If JavaParser implementation changes, this breaks

**Fix**:
```python
import javalang  # Explicit import at top
```

---

### 🟢 ISSUE 8: No Validation of Coupling Data
**Location**: `evolutionary_miner.py:123-138`

**Missing checks**:
1. No validation that coupling strengths sum correctly
2. No check for NaN values from sqrt(0)
3. No warning if all methods filtered out (min_commits too high)
4. No diagnostic metrics returned

**Example problematic case**:
```python
# If window_months = 1 and min_commits = 10
# But file only has 8 commits total
# Result: Empty evolutionary data with no warning
```

**Fix**:
```python
if len(evo_data.method_names) == 0:
    self.logger.warning(
        f"No methods found with >= {min_commits} commits in {window_months} months. "
        f"Total commits: {len(commits)}. Consider lowering min_commits or increasing window_months."
    )
```

---

## Graph Fusion Issues

### 🟡 ISSUE 9: Alpha Parameter Semantics
**Location**: `graph_builder.py:118-199`

**Current implementation**:
```python
# alpha=1.0 means 100% static
# alpha=0.0 means 100% evolutionary
fused_weight = alpha * static_weight + (1 - alpha) * evo_weight
```

**Config says**:
```yaml
fusion:
  alpha: 1.0  # Full static, zero evolutionary!
```

**Problem**:
- With alpha=1.0, **evolutionary coupling ignored entirely**
- All that Git mining wasted!
- User likely doesn't understand alpha semantics

**Expected behavior**:
- Alpha should default to 0.5 (equal weight)
- Or better: adaptive alpha based on data quality
  ```python
  if G_evo.number_of_edges() == 0:
      alpha = 1.0  # No evolutionary data, use static only
  elif G_static.number_of_edges() == 0:
      alpha = 0.0  # No static data, use evolutionary only
  else:
      alpha = 0.5  # Both available, equal weight
  ```

---

### 🟡 ISSUE 10: Normalization Loses Information
**Location**: `graph_builder.py:153-183`

**Problem**:
```python
max_static = max(static_weights) if static_weights else 1.0
max_evo = max(evo_weights) if evo_weights else 1.0

# Normalize to [0, 1]
static_weight = G_static[u][v]['weight'] / max_static
evo_weight = G_evo[u][v]['weight'] / max_evo
```

**Issue**:
- Max normalization makes **strongest edge = 1.0** in each graph
- If static has edge weights [0.1, 0.2, 1.0] → normalized [0.1, 0.2, 1.0]
- If evo has edge weights [0.01, 0.02, 0.03] → normalized [0.33, 0.67, 1.0]
- Weak evolutionary coupling (0.03) becomes artificially strong (1.0)!

**Better approach** - MinMax normalization:
```python
min_static = min(static_weights) if static_weights else 0.0
max_static = max(static_weights) if static_weights else 1.0

static_weight = (weight - min_static) / (max_static - min_static)
```

Or **Z-score normalization** to preserve distribution:
```python
mean_static = np.mean(static_weights)
std_static = np.std(static_weights)
static_weight = (weight - mean_static) / std_static
```

---

### 🟡 ISSUE 11: Edge Threshold Applied After Fusion
**Location**: `graph_builder.py:186-192`

**Code**:
```python
fused_weight = alpha * static_weight + (1 - alpha) * evo_weight

# Only add edge if above threshold
if fused_weight >= edge_threshold:
    G_fused.add_edge(u, v, weight=fused_weight, ...)
```

**Problem**:
- Threshold (0.05) applied to **fused** weight
- But fused weight is blend of normalized values
- An edge with static=0.1, evo=0.0 → fused=0.1*1.0 + 0.9*0.0 = 0.1
- Gets kept even though evo coupling is zero

**Expected**:
- Threshold should consider **source** of weight
- Option 1: Require minimum in **either** graph
  ```python
  if static_weight >= threshold or evo_weight >= threshold:
  ```
- Option 2: Require minimum in **both** graphs
  ```python
  if static_weight >= threshold and evo_weight >= threshold:
  ```
- Option 3: Separate thresholds
  ```python
  if static_weight >= static_threshold or evo_weight >= evo_threshold:
  ```

---

## Performance and Caching Issues

### ⚠️ ISSUE 12: Cache Key Doesn't Include min_commits
**Location**: `evolutionary_miner.py:334-337`

**Code**:
```python
def _get_cache_key(self, class_file: str, window_months: int, repo_signature: str) -> str:
    key_str = f"{class_file}:{window_months}:{repo_signature}"
    return hashlib.md5(key_str.encode()).hexdigest()
```

**Missing**: `min_commits` parameter!

**Problem**:
1. User runs with `min_commits=2` → cached
2. User runs with `min_commits=10` → **returns cached data from min_commits=2**!
3. Wrong results

**Fix**:
```python
key_str = f"{class_file}:{window_months}:{min_commits}:{repo_signature}"
```

---

### ⚠️ ISSUE 13: repo_signature Computation is Expensive
**Location**: `evolutionary_miner.py:385-402`

**Code**:
```python
def _get_repo_signature(self, repo: Repo, class_file: str) -> str:
    head_commit = repo.head.commit.hexsha  # Git operation
    blob = tree / class_file  # Tree traversal
    file_signature = blob.hexsha  # Hash computation
```

**Issues**:
1. Called for **every** cache check
2. Git operations are slow (100-200ms each)
3. For CollectionUtils with 0.034s mining time, signature might take longer!

**Optimization**:
```python
# Cache the signature for the session
if not hasattr(self, '_repo_signatures'):
    self._repo_signatures = {}

sig_key = (repo_path, class_file)
if sig_key not in self._repo_signatures:
    self._repo_signatures[sig_key] = self._compute_signature(repo, class_file)

return self._repo_signatures[sig_key]
```

---

## Integration and Data Quality Issues

### ⚠️ ISSUE 14: No Logging of Mining Statistics
**Location**: `pipeline.py:334-367`

**Current logging**:
```python
self.logger.info("\n[Stage 2/6] Mining evolutionary coupling from Git history...")
# ... mining happens ...
# No stats logged!
```

**What's missing**:
- How many commits analyzed
- How many methods found in history
- How many co-change pairs detected
- Coupling strength distribution
- Cache hit/miss

**Impact**:
- User sees "Mining completed in 0.034s" (suspiciously fast → cached?)
- No visibility into data quality
- Can't debug why fusion produces poor results

**Fix**:
```python
evo_data = self.evolutionary_miner.mine_method_cochanges(...)

self.logger.info(
    f"Evolutionary mining results:\n"
    f"  Total commits: {evo_data.total_commits}\n"
    f"  Methods found: {len(evo_data.method_names)}\n"
    f"  Co-change pairs: {len(evo_data.cochange_matrix)}\n"
    f"  Avg coupling: {np.mean(list(evo_data.coupling_strengths.values())) if evo_data.coupling_strengths else 0:.3f}\n"
    f"  Max coupling: {max(evo_data.coupling_strengths.values()) if evo_data.coupling_strengths else 0:.3f}"
)
```

---

### ⚠️ ISSUE 15: Name Mismatch Between Static and Evolutionary
**Location**: `graph_builder.py:93-110` and `pipeline.py:393`

**Pipeline code**:
```python
# Build method name to signature mapping for evolutionary graph
method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
G_evo = self.graph_builder.build_evolutionary_graph(evo_data, method_map)
```

**Problem chain**:
1. Static graph uses **full signatures**: `"add(String, int)"`
2. Evolutionary mining extracts **names only**: `"add"`
3. method_map tries to match: `{"add": "add(String, int)"}`
4. **Collision on overloaded methods** - only one signature kept
5. Fusion creates edges for **wrong method pairs**

**Example**:
```java
// Static graph has these nodes:
add(String)
add(int, String)
add(Collection)

// Evolutionary mining finds:
"add" co-changes with "remove"

// method_map is:
{"add": "add(Collection)"}  // Last one wins!

// Fusion creates edge:
add(Collection) ↔ remove
// But maybe it was add(String) that co-changed!
```

**Impact**: Wrong edges in fused graph → bad clustering

---

### ⚠️ ISSUE 16: Git History Not Found Warning is Too Quiet
**Location**: `evolutionary_miner.py:97-101`

**Code**:
```python
commits = self._get_file_commits(repo, normalized_class_file, start_date, end_date)

if not commits:
    self.logger.warning(f"No commits found for {normalized_class_file} in the time window")
    return EvolutionaryData(class_file=normalized_class_file)
```

**Problem**:
- Returns **empty** EvolutionaryData
- But fusion proceeds normally
- User never knows evolutionary coupling was zero
- Graph appears to work but is actually 100% static

**CollectionUtils example**:
- Suspiciously fast (0.034s) suggests cache hit or no commits
- But no indication to user that evolutionary data is missing
- All clustering based on static only (which we know is weak)

**Fix**:
```python
if not commits:
    self.logger.error(
        f"❌ No commits found for {normalized_class_file} in the time window!\n"
        f"   This likely means:\n"
        f"   - File path is incorrect relative to repo root\n"
        f"   - Time window ({window_months} months) is too narrow\n"
        f"   - File was recently added to repository\n"
        f"   Evolutionary coupling will be ZERO - clustering may be poor."
    )
```

---

## Root Cause Analysis: Why CollectionUtils Has Poor Results

Based on Stage 1 + Stage 2 analysis:

### The Compounding Problems:

1. **Stage 1**: Weak static dependencies
   - Only 79 edges for 71 methods
   - Name-based matching misses overloads
   - Missing static call detection

2. **Stage 2**: Broken evolutionary coupling
   - **alpha=1.0** → evolutionary data ignored completely!
   - Even if alpha was 0.5, name-only matching creates wrong edges
   - 0.034s mining time suggests cache hit or no commits

3. **Stage 3**: Flawed fusion
   - Garbage in, garbage out
   - Max normalization amplifies weak signals
   - Wrong threshold semantics

4. **Result**: Sparse, incorrect graph
   - 79 edges, 39 components
   - Clustering impossible
   - Poor quality suggestions

### Expected vs Actual:

**If Stage 2 worked correctly**:
```
71 methods × 50 commits = 3,550 method changes
Expected co-change pairs: ~100-200
Expected evolutionary edges: ~50-100
Combined with fixed static (200 edges): ~250-300 total edges
→ Good clustering possible
```

**Actual CollectionUtils**:
```
Evolutionary: ??? (alpha=1.0 so doesn't matter)
Static: 79 edges (broken)
Fused: 79 edges (alpha=1.0)
→ Clustering impossible
```

---

## Recommendations

### 🎯 High Priority Fixes:

1. **Fix alpha parameter** (ISSUE #9) - **5 minutes**
   - Change config default to 0.5
   - Add adaptive alpha based on data availability
   - **Immediate impact**: Actually use evolutionary coupling

2. **Fix method signature extraction** (ISSUE #1) - **30 minutes**
   - Extract full signatures from Git history, not just names
   - Use same signature format as static analysis
   - **Impact**: Correct edge mappings

3. **Add diagnostic logging** (ISSUE #14) - **15 minutes**
   - Log mining statistics
   - Warn when no commits found
   - **Impact**: User visibility into data quality

4. **Fix cache key** (ISSUE #12) - **5 minutes**
   - Include min_commits in cache key
   - **Impact**: Correct caching behavior

### 🎯 Medium Priority:

5. **Improve coupling formula** (ISSUE #6) - **1-2 hours**
   - Implement asymmetric support or Jaccard
   - Add time decay
   - **Impact**: Better coupling strength estimation

6. **Fix normalization** (ISSUE #10) - **30 minutes**
   - Use MinMax or Z-score normalization
   - **Impact**: Don't amplify weak signals

7. **Handle merge commits** (ISSUE #4) - **1 hour**
   - Detect and handle multi-parent commits
   - **Impact**: More complete coupling data for real repos

### 🎯 Low Priority (Future Work):

8. Replace regex-based parsing (ISSUE #2, #3)
9. Add coupling validation (ISSUE #8)
10. Optimize signature computation (ISSUE #13)
11. Fix edge threshold semantics (ISSUE #11)

---

## Minimal Viable Fix (20 minutes)

**Critical path to immediately improve results**:

```python
# 1. Fix alpha in config/config.yaml (1 minute)
fusion:
  alpha: 0.5  # Was 1.0 - NOW USE EVOLUTIONARY DATA!

# 2. Add logging in pipeline.py (5 minutes)
evo_data = self.evolutionary_miner.mine_method_cochanges(...)
self.logger.info(
    f"Evolutionary: {len(evo_data.method_names)} methods, "
    f"{len(evo_data.coupling_strengths)} couplings"
)

# 3. Fix cache key in evolutionary_miner.py (2 minutes)
key_str = f"{class_file}:{window_months}:{min_commits}:{repo_signature}"

# 4. Add error for missing commits (5 minutes)
if not commits:
    self.logger.error(f"❌ No commits found! File: {normalized_class_file}")

# 5. Add javalang import (1 minute)
import javalang
```

**Expected improvement**:
- Alpha fix: Actually use evolutionary coupling
- Logging: User sees what's happening
- Cache fix: Correct behavior across runs
- Error visibility: Debug missing Git data

**Impact on CollectionUtils**:
- If Git history available: +50-100 edges from evolutionary
- Total: 79 (static) + 75 (evo) × 0.5 (alpha) → ~150 edges
- Still not great (need Stage 1 fix too), but 2x improvement

---

## Testing Recommendations

### Unit Tests Needed:

1. **Test overloaded method handling**:
   ```java
   class TestClass {
       void add(String s) { }
       void add(int i) { }
   }
   // Verify both methods tracked separately in evolutionary data
   ```

2. **Test merge commit handling**:
   - Create repo with merge commit
   - Verify changes from both parents detected

3. **Test coupling formula**:
   - Known co-change counts → verify coupling strength
   - Edge cases: method with 0 commits, 1 commit

### Integration Tests:

Test on real repos with known characteristics:
- **Actively developed repo** (100+ commits) → verify mining works
- **Repo with merge commits** → verify merge handling
- **Repo with overloaded methods** → verify signature matching

---

## Summary

**Stage 2 has serious issues** that compound Stage 1 weaknesses:

### Critical Flaws:
1. **Name-only method matching** creates wrong evolutionary edges (same as Stage 1)
2. **Alpha=1.0 default** completely ignores evolutionary coupling
3. **Regex-based method detection** is fragile and inaccurate
4. **Brace counting** is fundamentally broken for finding method boundaries
5. **No diagnostic logging** leaves user blind to data quality

### Impact on CollectionUtils:
- Alpha=1.0 means evolutionary data completely unused
- Even if used, name-only matching would create wrong edges
- Combined with Stage 1 weakness: sparse, incorrect graph
- Result: Poor clustering, failed verifications

### Priority:
**Fix alpha parameter first** (5 minutes) - this is blocking all evolutionary coupling!

Then tackle method signature extraction (30 minutes) to get correct edge mappings.

With these two fixes + Stage 1 minimal fix, CollectionUtils should go from:
- **Current**: 79 edges, 39 components
- **After fixes**: 250-350 edges, 8-12 components
- **Result**: Effective clustering becomes possible
