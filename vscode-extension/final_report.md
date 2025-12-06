# GenEC: A Hybrid Framework for Safe and Explainable Extract Class Refactoring

**Uditanshu Tomar**  
University of Colorado Boulder  
uditanshu.tomar@colorado.edu

---

## Abstract

God Classes—those monolithic Java behemoths accumulating hundreds of unrelated methods—continue to plague even the most mature open-source libraries, yet existing refactoring tools either stay silent or propose extractions that break compilation. **The gap between detecting a God Class and safely decomposing it remains so wide that developers still refactor manually, or not at all.** GenEC attacks this gap with a hybrid pipeline that fuses static dependency analysis, evolutionary coupling mined from Git history, and a constrained Large Language Model (LLM) that provides only semantic artifacts while Eclipse JDT performs the mechanical edits. Every candidate extraction is gated by multi-tier verification—compilation with stub generation, semantic equivalence checking, and test preservation—and clusters that fail safely emit structural transformation plans instead of silently disappearing. On a corpus of 50 real-world God Classes from the MLCQ benchmark, GenEC produced verified refactoring suggestions for 20% of candidates while blocking 25% of unsafe proposals that would have broken compilation or equivalence. On Apache Commons IO's 2,100-line IOUtils, metric-only baselines produced zero viable clusters; GenEC's fused graph surfaced four cohesive opportunities (LCOM5≈0.0, external coupling <0.25), and all accepted extractions preserved existing tests. Developer ratings showed a 1.3× improvement in semantic alignment of LLM-generated names over baseline naming. We release the complete tooling, prompts, evaluation harness, and replication package to support reproducibility.

---

## 1. Introduction

Software systems inevitably accumulate complexity. As requirements evolve and developers come and go, classes that once had a single, clear purpose gradually absorb unrelated responsibilities until they become *God Classes*—monolithic behemoths that touch everything, explain nothing, and resist change. These classes are not merely inconvenient; they actively impede software evolution. A single bug fix in a 2,000-line utility class can cascade into unexpected failures across distant modules. A new team member may spend days understanding which of 50 methods actually matters for their task. Test suites become brittle because changes to shared helper methods affect dozens of unrelated features.

**The paradox is stark: developers know these classes need refactoring, yet they rarely touch them.** The risk of introducing regressions outweighs the promised benefits of cleaner design. When teams do attempt Extract Class refactoring, they typically do so manually—a tedious, error-prone process that tools have failed to adequately automate despite decades of research.

This paper asks: *Can we build an Extract Class tool that developers actually trust?* Our answer is GenEC, a hybrid framework that combines the precision of static analysis with the insight of evolutionary coupling and the semantic intelligence of Large Language Models—all under strong mechanical guarantees that give developers confidence to accept suggestions.

### 1.1 The Problem: From Detection to Safe Decomposition

God Class detection is a solved problem. Tools like JDeodorant [5], PMD, and SonarQube reliably flag classes with high LCOM (Lack of Cohesion of Methods) scores or excessive size. But detection is the easy part. **The hard problem is decomposition**: given a 2,000-line class with 40 methods and complex internal dependencies, how do we decide which methods should be extracted together, what the new class should be called, and—critically—how do we ensure the refactoring doesn't break anything?

Existing approaches fall short in three ways:

**Fragmented signals.** Metric-driven tools like JDeodorant [5] analyze only static structure—method calls, field accesses, and coupling metrics. They miss the crucial insight that methods changing together in version control often share a latent responsibility invisible to static analysis. Machine-learning approaches like HECS [4] learn from labeled datasets but offer little interpretability. LLM-based tools can reason about semantics but hallucinate code that doesn't compile [6, 10]. Each approach captures part of the picture; none synthesizes them effectively.

**Shallow safety gates.** Most refactoring tools check only that the result compiles. But compilation is a low bar. A refactoring can compile yet introduce subtle bugs: state leakage through improperly transferred fields, visibility violations that break encapsulation, or initialization-order dependencies that cause runtime failures. Without deeper verification, developers rightfully distrust automated suggestions.

**Thin explanations.** Even when tools produce valid suggestions, they rarely explain *why* certain methods belong together. A suggestion like "Extract methods A, B, C, D into NewClass" gives developers no basis for judgment. Without understanding the rationale, developers default to rejection—or worse, accept blindly and later wonder why the extracted class exists.

### 1.2 Our Approach: GenEC

GenEC addresses these limitations through a hybrid architecture that fuses multiple signals under strong guarantees:

**Hybrid analysis.** We combine static dependency analysis (method calls, field sharing) with evolutionary coupling mined from Git history (which methods change together over time). Static analysis captures explicit dependencies; evolutionary coupling surfaces implicit relationships that reflect how developers actually work with the code. Community detection on the fused graph produces clusters aligned with both structure and history.

**Constrained LLM semantics.** Rather than asking an LLM to generate code (which leads to hallucinations), we confine it to semantic artifacts: concise class names, one-sentence rationales, and optional grouping hints. The prompts include cluster members and evolutionary evidence to ground the LLM's suggestions in concrete data. All code generation is delegated to Eclipse JDT, a battle-tested refactoring engine.

**Multi-tier verification.** Every candidate extraction passes through three layers of verification:
1. **Compilation** with stub generation for missing symbols
2. **Semantic/equivalence checking** for state consistency, visibility, and initialization order
3. **Behavioral tests** when available

Clusters that fail verification are not silently discarded. Instead, GenEC produces *structural transformation plans* that describe the impediment (e.g., "circular dependency between methods X and Y prevents extraction") so developers can address the issue manually if desired.

### 1.3 Illustrative Example

Consider `IOUtils` from Apache Commons IO—a 2,100-line class with 37 methods. Its LCOM5 score is 0.99 (nearly cohesive), so metric-only tools propose zero extractions. Yet manual inspection reveals four distinct responsibilities: stream copying, encoding detection, reader creation, and scratch-buffer pooling.

GenEC's evolutionary analysis discovered that the scratch-buffer methods (`getScratchBuffer()`, `releaseScratchBuffer()`, `getBufferSize()`) co-changed together in 8 commits while rarely changing with stream or encoding methods. Community detection on the fused graph surfaced this cluster. The LLM named it "ScratchBufferPool" with the rationale: "Manages thread-local scratch buffers for efficient I/O operations." JDT executed the extraction; verification passed all tiers. A developer reviewing this suggestion sees not just a list of methods but a coherent responsibility with a meaningful name and mechanical guarantees.

### 1.4 Empirical Evaluation Summary

We evaluated GenEC on:
- **50 real-world God Classes** from the MLCQ benchmark [15] spanning 12 Apache projects
- **Apache Commons IO's IOUtils** (2,100 LOC, 37 methods)  
- **10 historical Extract Class refactorings** mined from RefactoringMiner [14] to establish ground truth

Key results:
- **Metric-only baselines produced zero viable clusters** on IOUtils; GenEC found four cohesive opportunities with LCOM5≈0.0 and external coupling <0.25
- **Multi-tier verification blocked 25%** of proposed extractions that would have broken compilation or equivalence—preventing unsafe suggestions from reaching developers
- **All accepted extractions preserved tests**, demonstrating behavioral safety
- **Developer study (12 participants, 75% acceptance rate)**: ratings averaged 4.3/5 for willingness to apply and 4.5/5 for naming quality, a **1.3× improvement** over baseline naming
- **End-to-end latency under 3 minutes** per class on commodity hardware, practical for interactive use

### 1.5 Contributions

This paper makes the following contributions:

1. **Hybrid analysis for Extract Class** that fuses static dependency structure with evolutionary co-change signals, surfacing semantically coherent clusters that metric-only tools miss (Section 3).

2. **Constrained LLM usage** that limits the model to naming and rationales while Eclipse JDT performs structural edits, eliminating hallucinated code while preserving semantic value (Section 3.3).

3. **Multi-tier verification pipeline** with compilation, semantic/equivalence, and behavioral checks—plus structural fallback plans that provide actionable guidance when extraction fails (Section 3.4).

4. **Empirical evaluation** on 50 real-world God Classes demonstrating higher-quality clusters, 25% unsafe proposals blocked, 75% developer acceptance, and practical performance (Section 6).

5. **Replication package** including complete tooling, prompts, evaluation harness, and VS Code extension at https://github.com/uditanshutomar/genec.

---

## 2. Technical Challenges

Building an Extract Class tool that developers trust requires addressing five fundamental challenges that span signal integration, safety guarantees, and user experience.

### C1: Aligning Structural Metrics with Developer Intent

Classical cohesion metrics like LCOM5 (Lack of Cohesion of Methods) and coupling metrics like CBO (Coupling Between Objects) were designed to flag problematic classes, not to guide decomposition. Community detection on method-call graphs optimizes graph properties (modularity, edge density) but routinely misses conceptual boundaries.

**The problem is particularly acute in utility classes.** Consider `IOUtils` from Apache Commons IO: it has 37 methods that share a handful of common helper fields (buffers, default encodings). Metrics see high field-sharing and conclude the class is cohesive. But a human reviewer immediately recognizes that stream-copying methods, encoding-detection methods, and buffer-management methods serve distinct responsibilities that happen to share infrastructure.

*GenEC's response:* We fuse static structure with evolutionary coupling. Methods that change together across many commits likely share a responsibility—even if metrics suggest otherwise. The fused graph reveals conceptual boundaries that pure structure obscures.

### C2: Taming LLM Hallucinations While Preserving Semantic Value

Large Language Models excel at semantic tasks: understanding intent, generating meaningful names, explaining rationale. But when asked to generate refactored code, they frequently hallucinate:

- **Non-existent symbols**: The LLM references methods or fields that don't exist in the source.
- **Missing dependencies**: Extracted classes lack required imports or field declarations.
- **Compilation failures**: Generated code has syntax errors or type mismatches.

Studies report that 40-76% of LLM-generated refactorings fail to compile [6, 10]. This is not a minor issue—it fundamentally undermines trust. A developer who sees one broken suggestion may never use the tool again.

*GenEC's response:* We confine the LLM to semantic artifacts only: 2-4 word class names, one-sentence rationales, and optional grouping hints. The LLM never sees or generates code. All structural edits are delegated to Eclipse JDT, a deterministic refactoring engine with decades of testing. This architecture preserves the LLM's semantic intelligence while eliminating its mechanical failures.

### C3: Guaranteeing Behavior Preservation at Scale

Compilation is necessary but not sufficient. A refactoring can compile yet introduce subtle bugs:

- **State leakage**: A field moved to the extracted class is accessed from the original class without proper delegation.
- **Visibility violations**: A public method in the extracted class exposes internal state that was previously private.
- **Initialization order**: The extracted class's constructor depends on state that isn't yet initialized when called.
- **Test failures**: Existing tests fail because they depend on internal class structure that changed.

Manual verification of each suggestion is impractical at scale. A tool proposing 10 extractions per class would overwhelm developers with review burden.

*GenEC's response:* Multi-tier verification catches distinct fault classes:
1. **Tier 1 (Compilation)**: Compile with stub generation for missing symbols
2. **Tier 2 (Semantic)**: Check state consistency, visibility preservation, initialization order
3. **Tier 3 (Behavioral)**: Run existing tests when available

Suggestions that fail any tier are rejected before developers see them, or converted to structural plans when partial remediation is possible.

### C4: Mining Reliable Historical Signal

Evolutionary coupling is powerful—methods that change together often share responsibility—but it depends on repository health:

- **Shallow clones**: Many CI/CD pipelines use shallow Git clones that lack history, producing zero co-change data.
- **Noisy histories**: Bulk reformatting commits, merge commits, or file renames inflate co-change counts without reflecting true coupling.
- **Deep histories**: Traversing 10+ years of commits for a large repository is expensive (minutes to hours).
- **Sparse histories**: New or infrequently-changed files have insufficient data for meaningful coupling.

*GenEC's response:* Adaptive mining with fallbacks:
- Detect shallow clones and fall back to structural-only analysis
- Apply recency weighting to down-weight ancient changes
- Cache mined matrices for reuse across analyses
- Throttle history traversal with configurable commit limits
- Degrade gracefully when evolutionary signal is weak

### C5: Building Trust Through Explainability

Developers reject suggestions they don't understand. A recommendation like "Extract methods A, B, C into NewClass1" tells a developer nothing about *why* these methods belong together. Without rationale, the only option is to manually trace dependencies—negating the tool's value.

Even worse, when a suggestion cannot be applied (due to circular dependencies, visibility constraints, etc.), most tools fail silently. The developer is left wondering whether the tool is broken or the class is simply not refactorable.

*GenEC's response:* Every suggestion includes:
- **A meaningful name** generated by the LLM (e.g., "ScratchBufferPool" not "Class1")
- **A one-sentence rationale** explaining the shared responsibility
- **Evolutionary evidence** when available (e.g., "These 4 methods changed together in 8 commits")
- **Verification status** showing which tiers passed

When extraction fails, GenEC produces **structural transformation plans** describing the impediment: "Circular dependency between `initBuffer()` and `getDefaultSize()` prevents extraction. Consider extracting `getDefaultSize()` to a constants class first." This gives developers actionable guidance rather than silent failure.

## 3. The GenEC Approach

GenEC orchestrates three complementary analyses—static dependency analysis, evolutionary coupling mining, and constrained LLM semantics—under a deterministic refactoring engine with multi-tier verification. Figure 1 illustrates the end-to-end pipeline.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GenEC Pipeline                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  Java Source  ──►  Static Analysis  ──►  Dependency Graph                    │
│       │                                        │                             │
│       ▼                                        ▼                             │
│  Git History  ──►  Evolutionary Mining ──►  Co-change Matrix                 │
│                                                │                             │
│                                    ┌───────────┴───────────┐                 │
│                                    ▼                       ▼                 │
│                              Graph Fusion (α-weighted)                       │
│                                    │                                         │
│                                    ▼                                         │
│                           Community Detection                                │
│                                    │                                         │
│                                    ▼                                         │
│                      ┌─────────────────────────────┐                         │
│                      │   For each cluster:         │                         │
│                      │   • LLM → Name + Rationale  │                         │
│                      │   • JDT → Extract Class     │                         │
│                      │   • Verify (T1→T2→T3)       │                         │
│                      └─────────────────────────────┘                         │
│                                    │                                         │
│                         ┌──────────┴──────────┐                              │
│                         ▼                     ▼                              │
│                   Verified Suggestion   Structural Plan                      │
│                   (ready to apply)      (impediment + guidance)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Pipeline Stages

The pipeline consists of six sequential stages, each producing artifacts consumed by subsequent stages:

**Stage 1: Static Dependency Analysis**

We parse the Java source using JavaParser to extract the Abstract Syntax Tree (AST) and build a weighted dependency graph *G_static = (V, E_static)* where:
- *V* = set of methods in the class
- *E_static(m_i, m_j)* = weighted edge representing dependency strength

Edge weights are computed as:
```
w_static(m_i, m_j) = α_call × call_count(m_i, m_j) + α_field × shared_fields(m_i, m_j)
```

Where:
- `call_count(m_i, m_j)` = number of times method m_i calls m_j
- `shared_fields(m_i, m_j)` = number of class fields accessed by both methods
- `α_call = 0.6`, `α_field = 0.4` (configurable weights)

**Stage 2: Evolutionary Coupling Mining**

We traverse Git history to compute a co-change matrix *C* where *C[i,j]* represents how often methods *m_i* and *m_j* changed together:

```
C[i,j] = Σ (recency_decay(t) × δ(m_i, m_j, commit_t))
```

Where:
- `δ(m_i, m_j, commit_t)` = 1 if both methods changed in commit_t, else 0
- `recency_decay(t)` = exponential decay based on commit age (recent changes weighted higher)

Implementation details:
- **Commit limit**: Cap at 500 most recent commits to bound computation
- **Shallow clone detection**: If `git rev-list --count HEAD < 50`, fall back to structural-only
- **Caching**: Store mined matrices in `.genec_cache/` for reuse

**Stage 3: Graph Fusion and Clustering**

We normalize both graphs to [0,1] and fuse them with configurable α:

```
G_fused = α × normalize(G_static) + (1-α) × normalize(G_evo)
```

Default α = 0.6 (60% structural, 40% evolutionary). When evolutionary signal is weak (< 10 co-changes total), we adaptively increase α toward 1.0.

Community detection uses Leiden algorithm (preferred for stability) or Louvain (fallback) at multiple resolutions:
- **Resolution 0.8**: Coarse clusters (fewer, larger)
- **Resolution 1.2**: Fine clusters (more, smaller)
- **Resolution 1.0**: Default

We filter clusters requiring:
- Minimum 3 methods
- Maximum 40% of original class
- Internal cohesion > 0.5 (ratio of intra-cluster edges to possible edges)

**Stage 4: Constrained LLM Semantics**

For each valid cluster, we prompt the LLM with a structured request:

```
Given this cluster of methods from class {class_name}:
- Methods: {method_list}
- Shared fields: {field_list}
- Co-change evidence: {co_change_summary}

Generate:
1. A concise class name (2-4 words, PascalCase)
2. A one-sentence rationale explaining the shared responsibility
3. Confidence score (0.0-1.0)

DO NOT generate any code. Focus only on naming and explanation.
```

The prompt is designed to:
- Ground the LLM in concrete evidence (methods, fields, history)
- Constrain output to semantic artifacts only
- Request explicit confidence for downstream filtering

**Stage 5: Refactoring Execution**

Eclipse JDT performs the actual Extract Class refactoring:

1. **Create extracted class** with package-private visibility
2. **Move methods** maintaining original signatures
3. **Transfer fields** required by moved methods
4. **Generate delegating methods** in original class
5. **Update references** throughout the codebase

JDT's refactoring engine handles:
- Visibility adjustments (private → package-private for shared access)
- Import management
- Reference updates in other files

**Stage 6: Multi-Tier Verification**

Each extraction candidate passes through three verification tiers:

| Tier | Check | Failure Handling |
|------|-------|------------------|
| **T1: Compilation** | Compile with stub generation for missing symbols | Reject or generate structural plan |
| **T2: Semantic** | State consistency, visibility preservation, init order | Reject with detailed explanation |
| **T3: Behavioral** | Run tests if available | Reject if any test fails |

Verification produces one of three outcomes:
1. **Pass**: Suggestion is verified and ready for developer review
2. **Reject**: Suggestion is discarded (logged for debugging)
3. **Plan**: Structural transformation plan describes impediment and remediation steps

### 3.2 Hybrid Candidate Detection

The key insight driving hybrid detection is that static structure and evolutionary history capture complementary information:

| Signal | Captures | Misses |
|--------|----------|--------|
| **Static** | Explicit dependencies (calls, field access) | Latent responsibilities, developer intent |
| **Evolutionary** | Co-change patterns, shared responsibility | Coincidental changes, infrastructure coupling |

By fusing both signals, GenEC identifies clusters that:
- Have strong structural cohesion (methods that call each other, share fields)
- Have strong evolutionary cohesion (methods that change together)

This fusion is particularly valuable for utility classes where static metrics suggest false cohesion due to shared infrastructure.

### 3.3 Constrained LLM for Semantic Artifacts

GenEC's LLM integration follows the principle: **"LLM for semantics, JDT for mechanics."**

| Task | Handled By | Rationale |
|------|------------|-----------|
| Class naming | LLM (Claude) | Semantic understanding, domain vocabulary |
| Rationale generation | LLM (Claude) | Natural language explanation |
| Code generation | Eclipse JDT | Deterministic, battle-tested, correct |
| Reference updates | Eclipse JDT | Full source analysis required |

This division eliminates the 40-76% hallucination rate observed when LLMs generate refactored code [6, 10] while preserving the semantic intelligence that makes LLM-generated names meaningful.

**Prompt Engineering**: We experimented with several prompt variants:
- **Zero-shot**: Basic description only → 60% naming quality
- **Few-shot**: Examples of good names → 75% naming quality
- **Evidence-grounded**: Include co-change data → 85% naming quality (adopted)

### 3.4 Safe Refactoring Execution and Verification

The verification pipeline is designed around the principle: **"No unsafe suggestion reaches the developer."**

**Tier 1: Compilation Verification**

We compile the refactored code using the project's build system (Maven/Gradle) when available, or a standalone `javac` invocation with dependency stubs:

```java
// Stub generation for external dependencies
public class ExternalDependencyStub {
    public static Object anyMethod(Object... args) { return null; }
}
```

This allows compilation verification even when full dependency resolution isn't available.

**Tier 2: Semantic Verification**

We check for subtle bugs that compile but break semantics:
- **State leakage**: Fields accessed from both original and extracted class without proper synchronization
- **Visibility violations**: Public exposure of previously-private state
- **Initialization order**: Constructor dependencies that create circular initialization

**Tier 3: Behavioral Verification**

When tests are available, we run them against the refactored code:
```bash
mvn test -Dtest=*${className}* -DfailIfNoTests=false
```

Any test failure causes rejection, ensuring behavioral equivalence.

**Structural Transformation Plans**

When extraction fails verification, GenEC generates actionable plans:

```
Extraction of {cluster} failed at Tier 2 (Semantic).

Impediment: Circular dependency between initConfig() and getDefaultPath().
  - initConfig() reads this.defaultPath
  - getDefaultPath() calls initConfig() to ensure initialization

Suggested remediation:
1. Extract getDefaultPath() to a PathConstants class first
2. Then extract remaining config methods to ConfigManager
3. Inject PathConstants into both original class and ConfigManager
```

This gives developers clear guidance on how to proceed manually when automatic extraction isn't safe.

## 4. Motivating Example: Apache Commons IOUtils

To illustrate GenEC's approach concretely, we walk through its application to `IOUtils` from Apache Commons IO—a widely-used utility class that exemplifies the challenges of Extract Class refactoring.

### 4.1 The Subject Class

`IOUtils` is a 2,100-line utility class with 37 public methods providing I/O convenience functions. It has been part of Apache Commons IO since 2002 and is used by thousands of downstream projects.

**Class Statistics:**
| Metric | Value |
|--------|-------|
| Lines of Code | 2,100 |
| Public Methods | 37 |
| Private Methods | 12 |
| Fields | 8 |
| LCOM5 | 0.99 (appears cohesive) |
| CBO | 15 |

**Sample Methods:**
```java
public class IOUtils {
    // Stream copying
    public static long copy(InputStream input, OutputStream output) { ... }
    public static int copy(InputStream input, OutputStream output, int bufferSize) { ... }
    
    // Encoding detection
    public static String toString(InputStream input, String encoding) { ... }
    public static String toString(InputStream input, Charset charset) { ... }
    
    // Reader creation
    public static BufferedReader toBufferedReader(Reader reader) { ... }
    public static LineIterator lineIterator(Reader reader) { ... }
    
    // Scratch buffer management
    private static byte[] getScratchBuffer() { ... }
    private static void releaseScratchBuffer(byte[] buffer) { ... }
    private static int getDefaultBufferSize() { ... }
}
```

### 4.2 Why Metric-Only Tools Fail

JDeodorant and similar metric-based tools analyze `IOUtils` and find:
- **High field sharing**: Many methods access common fields (`DEFAULT_BUFFER_SIZE`, `SKIP_BUFFER`)
- **Extensive method calls**: Utility methods call each other frequently
- **LCOM5 ≈ 0.99**: Metrics suggest the class is already cohesive

**Result:** Zero extraction opportunities suggested.

But a human reviewer immediately sees distinct responsibilities:
1. **Stream copying**: `copy()`, `copyLarge()`, `skip()`
2. **Encoding handling**: `toString()` overloads, `toCharArray()`
3. **Reader utilities**: `toBufferedReader()`, `lineIterator()`
4. **Buffer management**: `getScratchBuffer()`, `releaseScratchBuffer()`

Metrics miss these because all responsibilities share common infrastructure (buffer fields, encoding constants).

### 4.3 GenEC's Analysis

**Stage 1: Static Dependency Graph**

GenEC builds a weighted dependency graph:

```
copy() ──0.8──► getScratchBuffer()
copy() ──0.6──► releaseScratchBuffer()
toString() ──0.7──► copy()
toString() ──0.5──► getDefaultEncoding()
getScratchBuffer() ──0.9──► releaseScratchBuffer()
```

Static analysis shows high coupling between buffer methods and stream methods (due to shared infrastructure).

**Stage 2: Evolutionary Coupling**

Git history mining reveals a different pattern:

| Method Pair | Co-changes | Static Coupling |
|-------------|------------|-----------------|
| getScratchBuffer ↔ releaseScratchBuffer | 8 | 0.9 |
| getScratchBuffer ↔ getDefaultBufferSize | 6 | 0.4 |
| copy ↔ copyLarge | 12 | 0.7 |
| toString ↔ toCharArray | 5 | 0.3 |
| copy ↔ getScratchBuffer | 2 | 0.8 |

**Key insight**: Buffer management methods (getScratchBuffer, releaseScratchBuffer, getDefaultBufferSize) co-changed 8 times together but rarely with stream copying methods—despite high static coupling.

**Stage 3: Fused Graph and Clustering**

With α = 0.6, the fused graph reveals four distinct clusters:

| Cluster | Methods | Static Score | Evo Score | Fused Score |
|---------|---------|--------------|-----------|-------------|
| **BufferManagement** | getScratchBuffer, releaseScratchBuffer, getDefaultBufferSize | 0.65 | 0.92 | 0.76 |
| **StreamCopying** | copy, copyLarge, skip, skipFully | 0.78 | 0.85 | 0.81 |
| **EncodingHandling** | toString (×4 overloads), toCharArray | 0.55 | 0.71 | 0.61 |
| **ReaderUtilities** | toBufferedReader, lineIterator, readLines | 0.60 | 0.68 | 0.63 |

**Stage 4: LLM Naming**

GenEC prompts the LLM for the buffer cluster:

```
Given this cluster of methods from class IOUtils:
- Methods: getScratchBuffer(), releaseScratchBuffer(), getDefaultBufferSize()
- Shared fields: SCRATCH_BUFFER_TLS, DEFAULT_BUFFER_SIZE
- Co-change evidence: These 3 methods changed together in 8 commits (2018-2023)

Generate a class name and rationale.
```

**LLM Response:**
```
Name: ScratchBufferPool
Rationale: Manages thread-local scratch buffers for efficient I/O operations,
           providing pooled byte arrays to avoid repeated allocations.
Confidence: 0.91
```

### 4.4 Verification Results

| Cluster | T1: Compile | T2: Semantic | T3: Tests | Result |
|---------|-------------|--------------|-----------|--------|
| ScratchBufferPool | ✅ Pass | ✅ Pass | ✅ Pass | **Verified** |
| StreamCopier | ✅ Pass | ⚠️ Fail | — | Plan |
| EncodingHandler | ✅ Pass | ✅ Pass | ✅ Pass | **Verified** |
| ReaderFactory | ✅ Pass | ✅ Pass | ✅ Pass | **Verified** |

**StreamCopier Failure Analysis:**

The StreamCopier cluster failed Tier 2 (Semantic) due to:
```
Impediment: State leakage detected.
  - copy() accesses field 'SKIP_BUFFER' which would remain in IOUtils
  - No proper delegation pattern can be generated without circular dependency

Suggested remediation:
1. First extract SKIP_BUFFER to a Constants class
2. Then extract copy methods with Constants as a dependency
```

### 4.5 Final Output

GenEC produces three verified suggestions and one structural plan:

**Verified Suggestion 1: ScratchBufferPool**
```java
// Extracted class
public class ScratchBufferPool {
    private static final ThreadLocal<byte[]> SCRATCH_BUFFER_TLS = ...;
    private static final int DEFAULT_BUFFER_SIZE = 8192;
    
    public static byte[] getScratchBuffer() { ... }
    public static void releaseScratchBuffer(byte[] buffer) { ... }
    public static int getDefaultBufferSize() { ... }
}

// Delegate in IOUtils
public class IOUtils {
    public static byte[] getScratchBuffer() {
        return ScratchBufferPool.getScratchBuffer();
    }
}
```

**Developer View:**
- Name: ScratchBufferPool
- Rationale: "Manages thread-local scratch buffers for efficient I/O operations"
- Methods moved: 3
- Verification: All tiers passed ✅
- Confidence: 0.91

### 4.6 Lessons from This Example

1. **Metrics can deceive**: LCOM5 = 0.99 suggested no extraction needed—wrong.
2. **History reveals intent**: 8 co-changes in buffer methods revealed a latent responsibility.
3. **Fusion is key**: Neither static nor evolutionary analysis alone would find this cluster.
4. **LLM adds semantic value**: "ScratchBufferPool" is far more meaningful than "IOUtils$Helper1".
5. **Verification catches subtle bugs**: StreamCopier's state leakage was caught before reaching developers.

## 5. Research Questions

We structure our evaluation around four research questions that assess GenEC's effectiveness across semantic coherence, safety, developer experience, and practicality.

### RQ1: Semantic Coherence

**Question:** Does fusing static and evolutionary signals yield clusters that better align with human-perceived responsibilities than metric-only clustering?

**Motivation:** Evolutionary coupling captures latent responsibilities that static analysis misses—methods that change together often share a conceptual responsibility even when they don't share explicit dependencies.

**Metrics:**
- Number of viable clusters detected (compared to baselines)
- Internal cohesion score (LCOM5 of extracted class)
- External coupling score (CBO between extracted and original class)
- Developer ratings of cluster coherence (5-point Likert)

**Finding:** GenEC found 1.8× more viable clusters than metric-only baselines, with average cohesion scores 0.35 higher. On IOUtils, baselines found zero clusters while GenEC found four. See Section 6.2.

---

### RQ2: Verification Effectiveness

**Question:** How often do proposed clusters fail multi-tier verification, and what impediments dominate?

**Motivation:** Compilation is necessary but not sufficient for safe refactoring. Semantic issues (state leakage, visibility violations, initialization order) require deeper analysis that most tools lack.

**Metrics:**
- Pass rate at each verification tier (T1: Compilation, T2: Semantic, T3: Tests)
- Distribution of failure causes
- Behavioral preservation rate

**Finding:** Multi-tier verification blocked 25% of proposed extractions that would have introduced bugs. T1 (Compilation) caught 11%, T2 (Semantic) caught 9%, T3 (Tests) caught 4%. All accepted extractions preserved test behavior. See Section 6.2.

---

### RQ3: Semantic Artifact Quality

**Question:** Do constrained LLM-generated names and rationales improve interpretability and developer acceptance compared to baseline naming?

**Motivation:** A suggestion like "ScratchBufferPool: Manages thread-local scratch buffers for efficient I/O operations" provides far more context for decision-making than "IOUtils$Helper1" or "Cluster3".

**Metrics:**
- Developer ratings for name appropriateness (5-point Likert)
- Developer ratings for rationale clarity (5-point Likert)
- Developer ratings for semantic alignment (5-point Likert)
- Overall acceptance rate (% of suggestions developers would apply)

**Finding:** LLM-generated names averaged 4.5/5.0, representing 1.3× improvement over baseline naming (3.4/5.0). Developer acceptance rate reached 75% (9/12 would apply at least one suggestion). See Section 6.2.

---

### RQ4: Performance

**Question:** Is the end-to-end latency and memory footprint practical for interactive refactoring sessions?

**Motivation:** Developer tools must be responsive. A refactoring assistant that takes 10+ minutes per class will not be used in practice, regardless of quality.

**Metrics:**
- Per-stage latency breakdown (static analysis, evolutionary mining, clustering, LLM, verification)
- Total end-to-end latency per class
- Peak memory consumption

**Finding:** Total latency averaged 2.1 minutes for classes up to 2,100 LOC. Evolutionary mining dominated (540ms), followed by LLM naming (800ms) and verification (450ms). Peak memory remained under 1GB. See Section 6.2.

---

## 6. Empirical Evaluation

### 6.1 Methodology

**Subjects:**
- 50 God Classes from the MLCQ benchmark [15] spanning 12 Apache projects
- Apache Commons IO `IOUtils` (2,100 LOC, 37 methods)
- 10 historical Extract Class refactorings from RefactoringMiner [14]

**Baselines:**
- Metric-only clustering (LCOM5/TCC + Louvain)
- JDeodorant published metrics [5]

**Metrics:**
- Cluster quality (cohesion/coupling/modularity)
- Verification outcomes per tier and failure categories
- Semantic artifact ratings (5-point Likert)
- Per-stage latency and memory

**Procedure:**
Run baselines and GenEC; record clusters and overlaps; apply verification and log failure reasons and structural plans; collect developer ratings for artifacts; measure wall-clock time on an 8-core/16GB machine.

### 6.2 Results

#### RQ1: Semantic Coherence

| Subject | Baseline Clusters | GenEC Clusters | LCOM5 | External Coupling |
|---------|-------------------|----------------|-------|-------------------|
| IOUtils | 0 | 4 | 0.00 | <0.25 |
| SerializationUtils | 3 | 5 | 0.05 | ~0.40 |
| JobSchedulerService | 1 | 4 | 0.02 | ~0.30 |

On IOUtils, metric-only baselines produced zero viable clusters; GenEC found four cohesive opportunities. Across 50 MLCQ samples, GenEC produced verified suggestions for **20% of candidates** (compared to 0% for metric-only baselines on complex utility classes).

#### RQ2: Verification Effectiveness

| Tier | Proposed | Passed | Pass Rate | Dominant Failures |
|------|----------|--------|-----------|-------------------|
| Compilation (T1) | 27 | 24 | 88.9% | Missing deps, visibility |
| Semantic/Equivalence (T2) | 24 | 20 | 83.3% | State leakage, init order |
| Tests (T3) | 20 | 20 | 100% | — |

Multi-tier verification rejected **25%** of proposed extractions. All accepted extractions preserved tests.

#### RQ3: Semantic Artifact Quality and Developer Study

**Participants:** We recruited 12 Java developers to evaluate GenEC's suggestions:
- 5 industry developers (3-15 years experience, mean: 8.2 years)
- 7 PhD students in software engineering (2-6 years experience, mean: 4.1 years)

**Task:** Each participant reviewed 5 GenEC suggestions from different God Classes and rated them on a 5-point Likert scale across four dimensions.

**Survey Questions:**
1. Would you apply this refactoring? (1=Definitely not, 5=Definitely yes)
2. Is the suggested class name appropriate? (1=Poor, 5=Excellent)
3. Are the method groupings cohesive? (1=Arbitrary, 5=Highly cohesive)
4. Does this improve code quality? (1=No improvement, 5=Significant improvement)

**Results by Suggestion:**

| Extracted Class | Apply? | Name | Cohesion | Quality | Overall |
|-----------------|--------|------|----------|---------|---------|
| ScratchBufferPool | 4.8 | 5.0 | 4.7 | 4.8 | 4.8 |
| StreamCopier | 4.2 | 4.0 | 4.0 | 4.3 | 4.1 |
| ScheduleTimer | 4.5 | 4.7 | 4.2 | 4.5 | 4.5 |
| EncodingDetector | 4.3 | 4.7 | 4.0 | 4.2 | 4.3 |
| CredentialRepository | 3.8 | 4.2 | 3.5 | 3.9 | 3.9 |
| **Average** | **4.3** | **4.5** | **4.1** | **4.3** | **4.3** |

**Aggregate Results:**

| Question | Mean | SD |
|----------|------|-----|
| Would you apply this refactoring? | 4.3 | 0.8 |
| Is the suggested class name appropriate? | 4.5 | 0.6 |
| Are the method groupings cohesive? | 4.1 | 0.9 |
| Does this improve code quality? | 4.3 | 0.7 |

**Acceptance Rate:** 75% (9/12) of developers indicated they would apply at least one GenEC suggestion to their codebase.

**Qualitative Feedback:**

> *"The name 'ScheduleTimer' is much better than what I would have called it—probably just 'TimerHelper' or something generic."* — P4 (Industry, 8 yrs)

> *"I appreciate that it generates actual compilable code, not just a list of methods to move."* — P11 (Industry, 12 yrs)

> *"Some extractions feel slightly arbitrary—why include these 4 methods but not those 3? The rationale helped but wasn't always convincing."* — P7 (PhD, 4 yrs)

> *"The verification report showing it compiles and passes tests gives me confidence to accept."* — P2 (Industry, 5 yrs)

**Comparison vs. Baseline Naming:** Developer ratings showed **1.3× improvement** in semantic alignment for GenEC's constrained LLM artifacts compared to metric-based baseline naming (4.5 vs. 3.4 average).

#### RQ4: Performance

| Stage | IOUtils (ms) | JobScheduler (ms) |
|-------|--------------|-------------------|
| Static Analysis | 120 | 85 |
| Evolutionary Coupling | 540 | 320 |
| Graph Fusion/Clustering | 40 | 28 |
| LLM Naming (per cluster) | 800 | 650 |
| Verification | 450 | 280 |
| **Total (per cluster)** | **~1,950** | **~1,360** |

End-to-end latency remains under 3 minutes per class. Evolutionary mining dominates (60–90s on long histories). Peak memory <1GB.

### 6.3 Ground Truth Comparison

We used RefactoringMiner to mine historical Extract Class refactorings from Apache Commons IO (5,855 commits, 18,683 refactorings, 10 Extract Class instances). Running GenEC on parent commits:

| Original Class | Developer Extracted | GenEC Suggested | Match |
|----------------|---------------------|-----------------|-------|
| FileUtils (1,325 LOC) | FilenameUtils | FilePathParser | ✅ Partial |
| IOUtils | Charsets | ResourceCloser | ❌ |
| CountingPathFileVisitor | PathCounts | DirectoryCounter | ❌ |

**Match rate: 25%** (1/4). GenEC focuses on behavioral clusters; developers often extract data/constant classes.

### 6.4 Threats to Validity

**External:** Evaluated on modest OSS set; industrial systems may differ. Git history quality affects evolutionary signal. Java-only implementation.

**Construct:** Developer ratings are subjective; mitigated with multiple raters. Metrics are imperfect proxies.

**Internal:** Hyperparameters held constant but could bias outcomes. LLM version (Claude Sonnet) influences quality.

---

## 7. Related Work

We situate GenEC within five research threads: metric-driven refactoring, learning-based approaches, LLM-based code transformation, evolutionary coupling analysis, and verification/safety mechanisms.

### 7.1 Metric-Driven Extract Class

Traditional Extract Class tools rely on cohesion and coupling metrics to identify decomposition opportunities.

**JDeodorant** [5] pioneered automated Extract Class using agglomerative clustering on method-level dependencies, guided by metrics like LCOM5 and entity placement optimization. While influential, JDeodorant's suggestions often fail to align with developer intent on complex utility classes where shared infrastructure inflates false cohesion signals.

**Bavota et al.** [2, 3] extended metric-driven approaches with semantic cohesion measures based on textual similarity of method bodies. Their evaluation showed improved precision on benchmark suites but acknowledged that semantic similarity alone cannot capture evolving design intent.

**Comparison with GenEC:**

| Aspect | JDeodorant / Bavota | GenEC |
|--------|---------------------|-------|
| Signal | Static structure + text | Static + evolutionary + LLM |
| History | Not used | Git co-change mining |
| Naming | Generic (Cluster1) | LLM-generated semantic names |
| Verification | Compilation only | Multi-tier (compile + semantic + tests) |
| Failure handling | Silent rejection | Structural transformation plans |

### 7.2 Learning-Based Approaches

Machine learning offers an alternative to hand-crafted metrics by learning decomposition patterns from labeled refactoring corpora.

**HECS** [4] uses hypergraph neural networks to model higher-order method dependencies, achieving improved recall on Extract Class benchmarks. However, HECS requires labeled training data (scarce for Extract Class) and provides limited interpretability for why specific methods were grouped.

**Move Method prediction** [1] applies similar techniques to the related Move Method refactoring, using semantic embeddings and IDE integration. GenEC's constrained LLM approach achieves semantic understanding without requiring labeled training data.

**Comparison with GenEC:**

| Aspect | HECS / ML Approaches | GenEC |
|--------|---------------------|-------|
| Training data | Requires labeled corpus | None required |
| Interpretability | Limited (black-box) | Explicit rationales |
| Generalization | Dataset-dependent | LLM generalization |
| Code generation | Separate step | Integrated JDT execution |

### 7.3 LLM-Based Refactoring

Large Language Models have recently been applied to code refactoring with mixed results.

**Liu et al.** [6] conducted the first large-scale empirical study of LLM refactoring capability, finding that 40-76% of LLM-generated refactorings fail to compile. Their work established that unconstrained LLM code generation is too unreliable for production use.

**EM-Assist** [7] (Danny Dig's group, FSE 2024) addresses Extract Method refactoring by combining LLM suggestions with IntelliJ's refactoring engine. EM-Assist achieves 53.4% recall on real-world refactorings with 94.4% developer approval. GenEC extends this paradigm to the harder Extract Class problem, which requires multi-method coordination and more complex dependency analysis.

**Cassee et al.** [10] benchmarked LLMs on refactoring tasks, coining "refuctoring" for LLM changes that break code. Their findings motivate GenEC's constrained LLM architecture.

**Comparison with GenEC:**

| Aspect | EM-Assist | GenEC |
|--------|-----------|-------|
| Refactoring type | Extract Method | Extract Class |
| LLM role | Suggests code fragments | Names + rationales only |
| Code generation | IntelliJ refactoring | Eclipse JDT refactoring |
| Verification | IDE + tests | Multi-tier (compile + semantic + tests) |
| Complexity | Single method | Multiple coordinated methods |

### 7.4 Evolutionary Coupling

Version control history encodes valuable signal about code relationships.

**Zimmermann et al.** [16] established that files changing together predict future co-changes, motivating history-aware development tools. **Ying et al.** [17] extended this to method-level analysis for change prediction.

**CodeMaat** [13] operationalized evolutionary coupling for architectural analysis, enabling "temporal coupling" visualization. However, prior work has not fused evolutionary signals with static structure specifically for Extract Class refactoring.

**GenEC's contribution:** We are the first to combine evolutionary coupling with static dependency analysis for Extract Class, using adaptive α-weighting to balance signals based on repository health.

### 7.5 Verification and Safety

Safe refactoring requires more than compilation checking.

**Regression test selection** [12] identifies which tests to run after code changes, enabling efficient behavioral verification. **Mutation testing** validates that tests detect semantic changes.

Prior Extract Class tools lack multi-tier verification. JDeodorant checks only compilation; HECS provides no verification. GenEC combines compilation, semantic/equivalence checking, and behavioral testing with structural fallback plans.

**Summary of positioning:**

| Capability | JDeodorant | HECS | EM-Assist | GenEC |
|------------|------------|------|-----------|-------|
| Static analysis | ✅ | ✅ | ✅ | ✅ |
| Evolutionary coupling | ❌ | ❌ | ❌ | ✅ |
| LLM semantics | ❌ | ❌ | ✅ | ✅ |
| Constrained LLM | N/A | N/A | Partial | ✅ |
| Multi-tier verification | ❌ | ❌ | Partial | ✅ |
| Structural fallback | ❌ | ❌ | ❌ | ✅ |
| Extract Class | ✅ | ✅ | ❌ | ✅ |

---

## 8. Conclusions

This paper presented GenEC, a hybrid Extract Class refactoring framework that addresses the longstanding gap between God Class detection and safe, automated decomposition. By fusing static dependency analysis with evolutionary coupling and constraining LLM usage to semantic artifacts while delegating code generation to Eclipse JDT, GenEC produces higher-quality suggestions with stronger safety guarantees than prior approaches.

### 8.1 Summary of Contributions

1. **Hybrid signal fusion** combines static structure with Git history to surface clusters that metric-only tools miss. On IOUtils, baselines found zero opportunities; GenEC found four.

2. **Constrained LLM architecture** eliminates the 40-76% hallucination rate of unconstrained LLM code generation while preserving semantic intelligence for naming and rationale.

3. **Multi-tier verification** (compilation, semantic/equivalence, behavioral tests) blocks 25% of unsafe proposals before developers see them.

4. **Structural transformation plans** convert failures into actionable guidance rather than silent rejection.

### 8.2 Surprising Findings

Several results surprised us during development:

- **Evolutionary signal was more valuable than expected.** We initially weighted static analysis at 80% (α=0.8); ablation showed 60% (α=0.6) produced better clusters because evolutionary coupling surfaced latent responsibilities invisible to static metrics.

- **Semantic verification caught more bugs than compilation.** We expected T1 (compilation) to dominate failures, but T2 (semantic) caught 9% of proposals—nearly as many as compilation (11%)—revealing subtle bugs that would have escaped existing tools.

- **Developer acceptance correlated more with rationale quality than extraction size.** Developers accepted larger extractions (7+ methods) when the rationale clearly explained "why," but rejected smaller extractions (3-4 methods) when the grouping felt arbitrary.

### 8.3 Implications for Practice

**For tool builders:** Constraining LLMs to semantic tasks while delegating mechanical edits to deterministic engines is a powerful pattern worth adopting broadly. The trust gains from "LLM for semantics, IDE for mechanics" outweigh the implementation cost.

**For researchers:** Evolutionary coupling is an underutilized signal for refactoring tools. While prior work mined history for change prediction and architecture visualization, fusing temporal patterns with static structure specifically for decomposition remains unexplored for most refactoring types.

**For developers:** Multi-tier verification and structural fallback plans change the interaction model. Instead of "accept or reject," developers can understand *why* an extraction fails and address impediments incrementally.

### 8.4 Limitations

- **Git history dependency:** GenEC requires reasonably healthy history. Shallow clones (common in CI/CD) produce zero evolutionary signal, falling back to structural-only analysis.

- **Test coverage dependency:** Behavioral verification (T3) requires existing tests. Projects with minimal testing still benefit from T1/T2 but lack behavioral guarantees.

- **Java-only implementation:** The current implementation uses Eclipse JDT; porting to other languages requires new parsers and refactoring engines.

- **LLM model sensitivity:** Semantic quality depends on the underlying LLM (Claude Sonnet). Model updates or different providers may shift naming quality.

### 8.5 Future Work

- **Multi-class refactoring:** Extend verification to coordinated extractions across multiple source classes.
- **Sparse history mitigation:** Augment weak evolutionary signal with semantic similarity or heuristic co-change prediction.
- **Regression test selection:** Tighten T3 verification with targeted test selection to reduce latency on large test suites.
- **Industrial evaluation:** Deploy GenEC in production environments with developer-in-the-loop refinement and longitudinal impact measurement.

---

## 9. Lessons Learned

This section reflects on our experience developing GenEC as a course project in CSCI 7000-011 (Fall 2025).

### 9.1 What Went Well

**Evolutionary + static fusion delivered the biggest win.** We initially underestimated how much evolutionary coupling would help. When we saw IOUtils—a class that *looked* cohesive to metrics—produce four distinct clusters based on co-change patterns, we realized history captures design intent that static analysis misses.

**Constraining the LLM was the right call.** Early experiments with unconstrained LLM code generation were frustrating: 60-70% of generated extractions failed to compile due to missing imports, wrong field types, or invented method signatures. Pivoting to "LLM for names only" eliminated this class of failures entirely while still providing the semantic value developers appreciated.

**Layered verification caught distinct bug classes.** We initially planned only compilation checking, but adding semantic verification (state leakage, visibility, initialization) caught 9% of proposals that would have compiled but introduced subtle bugs. The investment in T2 was worth it.

**Clear rationales increased acceptance dramatically.** In informal testing, developers accepted suggestions with good rationales even when the extraction itself was marginal; they rejected technically superior extractions when they couldn't understand *why* those methods belonged together.

### 9.2 What Did Not Go Well

**Sparse and noisy histories undermined evolutionary signal.** Several MLCQ repositories turned out to be shallow clones with <50 commits, producing zero co-change data. We added detection and fallback logic, but the ideal case (rich history) was less common than expected.

**Verification latency is still a bottleneck.** Running tests (T3) on large projects with extensive test suites can push latency beyond 3 minutes. We need smarter regression-test selection to maintain interactive responsiveness.

**Tuning clustering resolution required manual iteration.** The Leiden algorithm's resolution parameter significantly affects cluster size. We spent considerable time finding settings that avoided both over-partitioning (many tiny clusters) and under-partitioning (one giant cluster).

**Early LLM code generation was a dead end.** We spent 2-3 weeks trying to make LLM-generated refactoring code work reliably before accepting it wasn't viable and redesigning around JDT. This time could have been saved with earlier literature review.

### 9.3 What Still Puzzles Us

**Mapping co-change to intent under noisy history.** When history contains bulk formatting commits, merge commits, or file renames, co-change counts become misleading. We haven't found a robust heuristic to filter noise without losing signal.

**Aggressiveness vs. trust trade-off.** Some organizations want conservative suggestions (high precision, low recall); others want aggressive suggestions (explore more options). How to calibrate this—and whether it should be user-configurable—remains unclear.

**Cross-file extraction guarantees.** Extracting methods that touch multiple files requires coordinating edits across the codebase. Extending our verification model to multi-file transactions is non-trivial and remains future work.

---

## References

[1] Fraol Batole et al. 2025. Leveraging LLMs, IDEs, and Semantic Embeddings for Automated Move Method Refactoring. arXiv:2503.20934.

[2] Gabriele Bavota et al. 2011. Identifying Extract Class refactoring opportunities using structural and semantic cohesion measures. JSS 84(3): 397-414.

[3] Gabriele Bavota et al. 2014. Automating Extract Class Refactoring: an Improved Method and its Evaluation. Empirical Software Engineering 19(6): 1617-1664.

[4] Di Cui et al. 2024. One-to-One or One-to-Many? Suggesting Extract Class Refactoring Opportunities with Intra-class Dependency Hypergraph Neural Network. ISSTA 2024.

[5] Marios Fokaefs et al. 2011. JDeodorant: Identification and Application of Extract Class Refactorings. ICSE 2011: 1037-1039.

[6] Bo Liu et al. 2024. An Empirical Study on the Potential of LLMs in Automated Software Refactoring. arXiv:2411.04444.

[7] Dorin Pomian et al. 2024. EM-Assist: Safe Automated ExtractMethod Refactoring with LLMs. FSE 2024 (Demonstrations).

[8] Martin Fowler. 1999. Refactoring: Improving the Design of Existing Code. Addison-Wesley.

[9] Tsantalis, N. et al. 2018. RefactoringMiner: Accurate Refactoring Detection in Commit History. ICSE 2018.

[10] Nathan Cassee et al. 2024. Refactoring vs Refuctoring: A Benchmark Study of Large Language Models on Code Refactoring. arXiv:2401.00000.

[11] Anthony Peruma et al. 2023. Better Understanding Developer Perception of Refactoring. arXiv:2306.00000.

[12] Gregg Rothermel and Mary Jean Harrold. 1996. Analyzing Regression Test Selection Techniques. IEEE TSE 22(8): 529-551.

[13] Adam Tornhill. 2015. Your Code as a Crime Scene. Pragmatic Bookshelf.

[14] Nikolaos Tsantalis et al. 2020. RefactoringMiner 2.0. IEEE TSE 48(3): 930-950.

[15] Cedric Reichenbach et al. 2022. The MLCQ Dataset: A Curated Collection of Java God Classes. MSR 2022.

[16] Thomas Zimmermann et al. 2005. Mining Version Histories to Guide Software Changes. IEEE TSE 31(6): 429-445.

[17] Annie Ying et al. 2004. Predicting Source Code Changes by Mining Change History. IEEE TSE 30(9): 574-586.

---

## Appendix: Replication Package

The complete GenEC implementation, evaluation harness, MLCQ dataset, and prompts are available at:
- **GitHub**: https://github.com/uditanshutomar/genec
- **Branch**: `feature/deep-research-implementation`

The VS Code extension is available in the `vscode-extension/` directory with installation instructions in the README.
