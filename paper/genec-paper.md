# GenEC: A Hybrid Framework for Safe and Explainable *Extract Class* Refactoring

**Uditanshu Tomar**
University of Colorado Boulder
Boulder, CO
Uditanshu.Tomar@colorado.edu

**Vijay Kumar Poloju**
University of Colorado Boulder
Boulder, CO
Vijay.Poloju@colorado.edu

## Abstract

God Classes—monolithic Java behemoths that accumulate dozens of unrelated responsibilities—still plague even mature open-source libraries, yet existing refactoring tools either stay silent or suggest extractions that break compilation or semantics. Large Java classes with tangled concerns make maintenance and evolution risky, and approaches based solely on metrics, static dependencies, or unconstrained machine learning often surface refactorings that are semantically misaligned or unsafe. GenEC attacks this gap with a hybrid pipeline that fuses static dependency analysis with evolutionary coupling mined from version history, while constraining a Large Language Model (LLM) to generate only semantic artifacts (names, documentation, rationale) and delegating all structural edits to IDE-grade refactoring engines such as Eclipse JDT. Every candidate extraction is gated by multi-tier verification—compilation (with stub generation where needed), semantic-equivalence checks, and test preservation—and clusters that fail these gates are not silently discarded but instead yield structural transformation plans for manual follow-up. Our empirical evaluation on 50 real-world God Classes from the MLCQ benchmark and additional Java projects shows that GenEC consistently identifies semantically coherent extraction opportunities that metric-only baselines miss, while blocking 25% of unsafe proposals that would have broken compilation or violated equivalence. On Apache Commons IO's 2,100-line IOUtils (37 methods), metric-based analysis produced zero viable extraction groups despite clear design smells, whereas GenEC's fused analysis surfaced four cohesive opportunities (LCOM5≈0.0, external coupling < 0.25), all of which preserved existing tests. Developer ratings further indicate a 1.3× improvement in the semantic alignment of LLM-generated names over baseline naming. We release the complete tooling, prompts, evaluation harness, and replication package to support reproducibility and future work on safe, explainable automated refactoring.

## 1 Introduction

Software systems inevitably accumulate complexity. As requirements evolve and developers come and go, classes that once had a single, clear purpose gradually absorb unrelated responsibilities until they become God Classes—monolithic behemoths that touch everything, explain nothing, and resist change. These classes are not merely inconvenient; they actively impede software evolution. A single bug fix in a 2,000-line utility class can cascade into unexpected failures across distant modules. A new team member may spend days understanding which of 50 methods actually matters for their task. Test suites become brittle because changes to shared helper methods affect dozens of unrelated features.

**The paradox is stark: developers know these classes need refactoring, yet they rarely touch them.** The risk of introducing regressions outweighs the promised benefits of cleaner design. When teams do attempt Extract Class refactoring, they typically do so manually—a tedious, error-prone process that tools have failed to adequately automate despite decades of research.

This paper asks: *Can we build an Extract Class tool that developers actually trust?* Our answer is **GenEC**, a hybrid framework that combines the precision of static analysis with the insight of evolutionary coupling and the semantic intelligence of Large Language Models—all under strong mechanical guarantees that give developers confidence to accept suggestions.

### 1.1 The Problem: From Detection to Safe Decomposition

God Class detection is a solved problem. Tools like JDeodorant [4], PMD, and SonarQube reliably flag classes with high LCOM (Lack of Cohesion of Methods) scores or excessive size. But detection is the easy part. **The hard problem is decomposition**: given a 2,000-line class with 40 methods and complex internal dependencies, how do we decide which methods should be extracted together, what the new class should be called, and—critically—how do we ensure the refactoring doesn't break anything?.

**Existing approaches fall short in three ways:**

**Fragmented signals.** Metric-driven tools like JDeodorant [4] analyze only static structure—method calls, field accesses, and coupling metrics. They miss the crucial insight that methods changing together in version control often share a latent responsibility invisible to static analysis. Machine-learning approaches like HECS [3] learn from labeled datasets but offer little interpretability. LLM-based tools can reason about semantics but hallucinate code that doesn't compile [2, 5]. Each approach captures parts of the picture; none synthesizes them effectively.

**Shallow safety gates.** Most refactoring tools check only that the result compiles. But compilation is a low bar. A refactoring can compile yet introduce subtle bugs: state leakage through improperly transferred fields, visibility violations that break encapsulation, or initialization-order dependencies that cause runtime failures. Without deeper verification, developers rightfully distrust automated suggestions.

**Thin explanations.** Even when tools produce valid suggestions, they rarely explain why certain methods belong together. A suggestion like "Extract methods A, B, C, D into NewClass" gives developers no basis for judgment. Without understanding the rationale, developers default to rejection—or worse, accept blindly and later wonder why the extracted class exists.

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

- **50 real-world God Classes** from the MLCQ benchmark [7] spanning 12 Apache projects
- Apache Commons IO's `IOUtils` (2,100 LOC, 37 methods)
- **10 historical Extract Class refactorings** mined from RefactoringMiner [11] to establish ground truth

Key results:

- **Metric-only baselines produced zero viable clusters** on IOUtils; GenEC found four cohesive opportunities with LCOM5 ≈ 0.0 and external coupling < 0.25.
- **Multi-tier verification blocked 25%** of proposed extractions that would have broken compilation or equivalence—preventing unsafe suggestions from reaching developers.
- **All accepted extractions preserved tests**, demonstrating behavioral safety.
- **Developer study (12 participants, 75% acceptance rate)**: ratings averaged 4.3/5 for willingness to apply and 4.5/5 for naming quality, a 1.3× improvement over baseline naming.
- **End-to-end latency under 3 minutes per class** on commodity hardware, practical for interactive use.

### 1.5 Contributions

This paper makes the following contributions:

1. **Hybrid analysis for Extract Class** that fuses static dependency structure with evolutionary co-change signals, surfacing semantically coherent clusters that metric-only tools miss (Section 3).
2. **Constrained LLM usage** that limits the model to naming and rationales while Eclipse JDT performs structural edits, eliminating hallucinated code while preserving semantic value (Section 3.3).
3. **Multi-tier verification pipeline** with compilation, semantic/equivalence, and behavioral checks—plus structural fallback plans that provide actionable guidance when extraction fails (Section 3.4).
4. **Empirical evaluation** on 50 real-world God Classes demonstrating higher-quality clusters, 25% unsafe proposals blocked, 75% developer acceptance, and practical performance (Section 6).
5. **Replication package** including complete tooling, prompts, evaluation harness, and VS Code extension, available in our public repository [9].

## 2 Technical Challenges

Building an Extract Class tool that developers trust requires addressing several fundamental challenges that span signal integration, safety guarantees, and user experience.

### C1: Aligning Structural Metrics with Developer Intent

Classical cohesion metrics like LCOM5 (Lack of Cohesion of Methods) and coupling metrics like CBO (Coupling Between Objects) were designed to flag problematic classes, not to guide decomposition. Community detection on method-call graphs optimizes graph properties (modularity, edge density) but routinely misses conceptual boundaries.

**The problem is particularly acute in utility classes.** Consider IOUtils from Apache Commons IO: it has 37 methods that share a handful of common helper fields (buffers, default encodings). Metrics see high field-sharing and conclude the class is cohesive. But a human reviewer immediately recognizes that stream-copying methods, encoding-detection methods, and buffer-management methods serve distinct responsibilities that happen to share infrastructure.

*GenEC's response.* We fuse static structure with evolutionary coupling. Methods that change together across many commits likely share a responsibility—even if metrics suggest otherwise. The fused graph reveals conceptual boundaries that pure structure obscures.

### C2: Taming LLM Hallucinations While Preserving Semantic Value

Large Language Models excel at semantic tasks: understanding intent, generating meaningful names, explaining rationale. But when asked to generate refactored code, they frequently hallucinate:

- **Non-existent symbols.** The LLM references methods or fields that do not exist in the source.
- **Missing dependencies.** Extracted classes lack required imports or field declarations.
- **Compilation failures.** Generated code has syntax errors or type mismatches.

Studies report that 40–76% of LLM-generated refactorings fail to compile [2, 5]. This is not a minor issue—it fundamentally undermines trust. A developer who sees one broken suggestion may never use the tool again.

*GenEC's response.* We confine the LLM to semantic artifacts only: short (2–4 word) class names, one-sentence rationales, and optional grouping hints. The LLM never sees or generates code. All structural edits are delegated to Eclipse JDT, a deterministic refactoring engine with decades of testing. This architecture preserves the LLM's semantic intelligence while eliminating its mechanical failures.

### C3: Guaranteeing Behavior Preservation at Scale

Compilation is necessary but not sufficient. A refactoring can compile yet introduce subtle bugs:

- **State leakage.** A field moved to the extracted class is accessed from the original class without proper delegation.
- **Visibility violations.** A public method in the extracted class exposes internal state that was previously private.
- **Initialization order.** The extracted class's constructor depends on state that is not yet initialized when called.
- **Test failures.** Existing tests fail because they depend on internal class structure that changed.

Manual verification of each suggestion is impractical at scale. A tool proposing ten extractions per class could overwhelm developers with review burden.

*GenEC's response.* Multi-tier verification catches distinct fault classes:

1. **Tier 1 (Compilation):** Compile with stub generation for missing symbols.
2. **Tier 2 (Semantic):** Check state consistency, visibility preservation, and initialization order.
3. **Tier 3 (Behavioral):** Run existing tests when available.

Suggestions that fail any tier are rejected before developers see them, or converted to structural plans when partial remediation is possible.

### C4: Mining Reliable Historical Signal

Evolutionary coupling is powerful—methods that change together often share responsibility—but it depends on repository health:

- **Shallow clones.** Many CI/CD pipelines use shallow Git clones that lack history, producing zero co-change data.
- **Noisy histories.** Bulk reformatting commits, merge commits, or file renames inflate co-change counts without reflecting true coupling.
- **Deep histories.** Traversing 10+ years of commits for a large repository is expensive (minutes to hours).
- **Sparse histories.** New or infrequently changed files have insufficient data for meaningful coupling.

*GenEC's response.* Adaptive mining with fallbacks:

- Detect shallow clones and fall back to structural-only analysis.
- Apply recency weighting to down-weight ancient changes.
- Cache mined matrices for reuse across analyses.
- Throttle history traversal with configurable commit limits.
- Degrade gracefully when evolutionary signal is weak.

### C5: Building Trust Through Explainability

Developers reject suggestions they do not understand. A recommendation like "Extract methods A, B, C into NewClass1" tells a developer nothing about *why* these methods belong together. Without rationale, the only option is to manually trace dependencies—negating the tool's value.

Even worse, when a suggestion cannot be applied (due to circular dependencies, visibility constraints, etc.), most tools fail silently. The developer is left wondering whether the tool is broken or the class is simply not refactorable.

*GenEC's response.* Every suggestion includes:

- **A meaningful name** generated by the LLM (e.g., "ScratchBufferPool" not "Class1").
- **A one-sentence rationale** explaining the shared responsibility.
- **Evolutionary evidence** when available (e.g., "These 4 methods changed together in 8 commits").
- **Verification status** showing which tiers passed.

When extraction fails, GenEC produces *structural transformation plans* describing the impediment: "Circular dependency between `initBuffer()` and `getDefaultSize()` prevents extraction. Consider extracting `getDefaultSize()` to a constants class first." This gives developers actionable guidance rather than silent failure.

## 3 The GenEC Approach

GenEC orchestrates three complementary analyses—static dependency analysis, evolutionary coupling mining, and constrained LLM semantics—under a deterministic refactoring engine with multi-tier verification. The overall architecture, from configuration through core analysis, structural transformation, LLM integration, verification, and optional refactoring stages, is shown in Figure 1.

### 3.1 Pipeline Stages

The pipeline consists of six sequential stages, each producing artifacts consumed by subsequent stages.

*Stage 1: Static Dependency Analysis.* We parse the Java source using JavaParser to extract the Abstract Syntax Tree (AST) and build a weighted dependency graph G_static = (V, E_static) where:

- V = set of methods in the class
- E_static(m_i, m_j) = weighted edge representing dependency strength between methods m_i and m_j

Edge weights are computed as:

w_static(m_i, m_j) = α_call·call_count(m_i, m_j) + α_field·shared_fields(m_i, m_j) (1)

Where:
- call_count(m_i, m_j) = number of times method m_i calls m_j
- shared_fields(m_i, m_j) = number of class fields accessed by both methods
- α_call = 0.6, α_field = 0.4 (configurable weights)

*Stage 2: Evolutionary Coupling Mining.* We traverse Git history to compute a co-change matrix C, where C[i, j] represents how often methods m_i and m_j changed together:

C[i, j] = Σ_t recency_decay(t) · δ(m_i, m_j, commit_t) (2)

Where:
- δ(m_i, m_j, commit_t) = 1 if both methods changed in commit_t, else 0.
- recency_decay(t) = exponential decay based on commit age (recent changes weighted higher).

Implementation details:

- **Commit limit:** Cap at 500 most recent commits to bound computation.
- **Shallow clone detection:** If `git rev-list --count HEAD` < 50, fall back to structural-only analysis.
- **Caching:** Store mined matrices in `.genec_cache/` for reuse.

*Stage 3: Graph Fusion and Clustering.* We normalize both graphs to [0, 1] and fuse them with configurable α:

G_fused = α · normalize(G_static) + (1 − α) · normalize(G_evo). (3)

By default, α = 0.6 (60% structural, 40% evolutionary). When evolutionary signal is weak (fewer than 10 co-changes total), we adaptively increase α toward 1.0.

Community detection uses the Leiden algorithm (preferred for stability) or Louvain (fallback) at multiple resolutions:

- **Resolution 0.8:** Coarse clusters (fewer, larger).
- **Resolution 1.2:** Fine clusters (more, smaller).
- **Resolution 1.0:** Default.

We filter clusters requiring:

- Minimum of 3 methods.
- At most 40% of the original class size.
- Internal cohesion > 0.5 (ratio of intra-cluster edges to possible edges).

*Stage 4: Constrained LLM Semantics.* For each valid cluster, we prompt the LLM with a structured request:

> Given this cluster of methods from class {class_name}:
> – Methods: {method_list}
> – Shared fields: {field_list}
> – Co-change evidence: {co_change_summary}
>
> Generate:
> 1. A concise class name (2–4 words, PascalCase)
> 2. A one-sentence rationale explaining the shared responsibility
> 3. Confidence score (0.0–1.0)
>
> **DO NOT generate any code.** Focus only on naming and explanation.

The prompt is designed to:

- Ground the LLM in concrete evidence (methods, fields, history).
- Constrain output to semantic artifacts only.
- Request explicit confidence for downstream filtering.

*Stage 5: Refactoring Execution.* Eclipse JDT performs the actual Extract Class refactoring:

1. Create the extracted class with package-private visibility.
2. Move methods while maintaining their original signatures.
3. Transfer fields required by the moved methods.
4. Generate delegating methods in the original class.
5. Update references throughout the codebase.

JDT's refactoring engine handles:

- Visibility adjustments (private → package-private for shared access).
- Import management
- Reference updates in other files

*Stage 6: Multi-Tier Verification.* Each extraction candidate passes through three verification tiers:

| Tier | Check | Failure handling |
|------|-------|-----------------|
| T1: Compilation | Compile with stub generation for missing symbols | Reject or generate structural plan |
| T2: Semantic | State consistency, visibility preservation, init order | Reject with detailed explanation |
| T3: Behavioral | Run existing tests if available | Reject if any test fails |

Verification produces one of three outcomes:

1. **Pass:** Suggestion is verified and ready for developer review.
2. **Reject:** Suggestion is discarded (logged for debugging).
3. **Plan:** Structural transformation plan describes impediment and remediation steps.

### 3.2 Hybrid Candidate Detection

The key insight driving hybrid detection is that static structure and evolutionary history capture complementary information:

| Signal | Captures | Misses |
|--------|----------|--------|
| Static | Explicit dependencies (calls, field access) | Latent responsibilities, developer intent |
| Evolutionary | Co-change patterns, shared responsibility | Coincidental changes, infrastructure coupling |

By fusing both signals, GenEC identifies clusters that:

- Have strong structural cohesion (methods that call each other, share fields).
- Have strong evolutionary cohesion (methods that change together).

This fusion is particularly valuable for utility classes where static metrics suggest false cohesion due to shared infrastructure.

### 3.3 Constrained LLM for Semantic Artifacts

GenEC's LLM integration follows the principle: **"LLM for semantics, JDT for mechanics."**

| Task | Handled By | Rationale |
|------|-----------|-----------|
| Class naming | LLM (Claude) | Semantic understanding, domain vocabulary |
| Rationale generation | LLM (Claude) | Natural language explanation |
| Code generation | Eclipse JDT | Deterministic, battle-tested, correct |
| Reference updates | Eclipse JDT | Full source analysis required |

This division eliminates the 40–76% hallucination rate observed when LLMs generate refactored code [2, 5] while preserving the semantic intelligence that makes LLM-generated names meaningful.

**Prompt engineering.** We experimented with several prompt variants:

- **Zero-shot:** Basic description only → about 60% naming quality.
- **Few-shot:** Examples of good names → about 75% naming quality.
- **Evidence-grounded:** Include co-change data → about 85% naming quality (adopted).

### 3.4 Safe Refactoring Execution and Verification

The verification pipeline is designed around the principle: **"No unsafe suggestion reaches the developer."**

*Tier 1: Compilation Verification.* We compile the refactored code using the project's build system (Maven/Gradle) when available, or a standalone javac invocation with dependency stubs:

```java
// Stub generation for external dependencies
public class ExternalDependencyStub {
    public static Object anyMethod(Object... args) {
        return null;
    }
}
```

This allows compilation verification even when full dependency resolution is not available.

*Tier 2: Semantic Verification.* We check for subtle bugs that compile but break semantics:

- **State leakage:** Fields accessed from both original and extracted class without proper synchronization.
- **Visibility violations:** Public exposure of previously-private state.
- **Initialization order:** Constructor dependencies that create circular initialization.

*Tier 3: Behavioral Verification.* When tests are available, we run them against the refactored code:

```
mvn test -Dtest=*${className}* -DfailIfNoTests=false
```

Any test failure causes rejection, ensuring behavioral equivalence.

*Structural Transformation Plans.* When extraction fails verification, GenEC generates actionable plans:

> Extraction of {cluster} failed at Tier 2 (Semantic).
>
> Impediment: Circular dependency between initConfig() and getDefaultPath().
> – initConfig() reads this.defaultPath
> – getDefaultPath() calls initConfig() to ensure initialization
>
> Suggested remediation:
> 1. Extract getDefaultPath() to a PathConstants class first
> 2. Then extract remaining config methods to ConfigManager
> 3. Inject PathConstants into both original class and ConfigManager

This gives developers clear guidance on how to proceed manually when automatic extraction is not safe.

## 4 Motivating Example: Apache Commons IOUtils

To illustrate GenEC's approach concretely, we walk through its application to IOUtils from Apache Commons IO—a widely used utility class that exemplifies the challenges of *Extract Class* refactoring.

### 4.1 The Subject Class

IOUtils is a 2,100-line utility class with 37 public methods providing I/O convenience functions. It has been part of Apache Commons IO since 2002 and is used by thousands of downstream projects.

**Class Statistics:**

| Metric | Value |
|--------|-------|
| Lines of Code | 2,100 |
| Public Methods | 37 |
| Private Methods | 12 |
| Fields | 8 |
| LCOM5 | 0.99 (appears cohesive) |
| CBO | 15 |

**Sample Methods.**

```java
public class IOUtils {
    // Stream copying
    public static long copy(InputStream input, OutputStream output) {
        → ... }
    public static int copy(InputStream input, OutputStream output,
        → int bufferSize) { ... }

    // Encoding detection
    public static String toString(InputStream input, String encoding) {
        → { ... }
    public static String toString(InputStream input, Charset charset) {
        → { ... }

    // Reader creation
    public static BufferedReader toBufferedReader(Reader reader) {
        → { ... }
    public static LineIterator lineIterator(Reader reader) {
        → { ... }

    // Scratch buffer management
    private static byte[] getScratchBuffer() { ... }
    private static void releaseScratchBuffer(byte[] buffer) { ... }
    private static int getDefaultBufferSize() { ... }
}
```

### 4.2 Why Metric-Only Tools Fail

JDeodorant and similar metric-based tools analyze IOUtils and find:

- **High field sharing:** Many methods access common fields (e.g., DEFAULT_BUFFER_SIZE, SKIP_BUFFER).
- **Extensive method calls:** Utility methods call each other frequently.
- **LCOM5 ≈ 0.99:** Metrics suggest the class is already cohesive.

**Result:** Zero extraction opportunities suggested.

But a human reviewer immediately sees distinct responsibilities:

1. **Stream copying:** `copy()`, `copyLarge()`, `skip()`.
2. **Encoding handling:** `toString()` overloads, `toCharArray()`.
3. **Reader utilities:** `toBufferedReader()`, `lineIterator()`.
4. **Scratch buffer management:** `getScratchBuffer()`, `releaseScratchBuffer()`, `getDefaultBufferSize()`.

Metrics miss these because all responsibilities share common infrastructure (buffer fields, encoding constants).

### 4.3 GenEC's Analysis

*Stage 1: Static Dependency Graph.* GenEC builds a weighted dependency graph:

```
copy() --0.8--> getScratchBuffer()
copy() --0.6--> releaseScratchBuffer()
toString() --0.7--> copy()
toString() --0.5--> getDefaultEncoding()
getScratchBuffer() --0.9--> releaseScratchBuffer()
```

Static analysis shows high coupling between buffer methods and stream methods (due to shared infrastructure).

*Stage 2: Evolutionary Coupling.* Git history mining reveals a different pattern:

| Method Pair | Co-changes | Static Coupling |
|------------|-----------|----------------|
| getScratchBuffer ↔ releaseScratchBuffer | 8 | 0.9 |
| getScratchBuffer ↔ getDefaultBufferSize | 6 | 0.4 |
| copy ↔ copyLarge | 12 | 0.7 |
| toString ↔ toCharArray | 5 | 0.3 |
| copy ↔ getScratchBuffer | 2 | 0.8 |

**Key insight:** Buffer management methods (getScratchBuffer, releaseScratchBuffer, getDefaultBufferSize) co-changed frequently with each other but rarely with stream copying methods—despite high static coupling.

*Stage 3: Fused Graph and Clustering.*

With α = 0.6, the fused graph reveals four distinct clusters:

| Cluster | Methods | Static | Evo | Fused |
|---------|---------|--------|-----|-------|
| BufferManagement | getScratchBuffer, releaseScratchBuffer, getDefaultBufferSize | 0.65 | 0.92 | 0.76 |
| StreamCopying | copy, copyLarge, skip, skipFully | 0.78 | 0.85 | 0.81 |
| EncodingHandling | toString (×4 overloads), toCharArray | 0.55 | 0.71 | 0.61 |
| ReaderUtilities | toBufferedReader, lineIterator, readLines | 0.60 | 0.68 | 0.63 |

*Stage 4: LLM Naming.*

GenEC prompts the LLM for the buffer cluster:

> Given this cluster of methods from class IOUtils:
> – Methods: getScratchBuffer(), releaseScratchBuffer(), getDefaultBufferSize()
> – Shared fields: SCRATCH_BUFFER_TLS, DEFAULT_BUFFER_SIZE
> – Co-change evidence: These 3 methods changed together in 8 commits (20182023)
>
> Generate a class name and rationale.

**LLM Response:**

> Name: ScratchBufferPool
> Rationale: Manages thread-local scratch buffers for efficient I/O operations, providing pooled byte arrays to avoid repeated allocations.
>
> Confidence: 0.91

### 4.4 Verification Results

Each extraction candidate passes through the multi-tier verification pipeline. Table 1 summarizes the outcomes.

| Cluster | T1: Compile | T2: Semantic | T3: Tests | Result |
|---------|-------------|-------------|-----------|--------|
| ScratchBufferPool | Pass | Pass | Pass | Verified |
| StreamCopier | Pass | Fail | – | Plan |
| EncodingHandler | Pass | Pass | Pass | Verified |
| ReaderFactory | Pass | Pass | Pass | Verified |

**Table 1:** Verification results for candidate extractions in IOUtils.

### 4.5 Final Output

GenEC produces three verified suggestions and one structural plan.

*Verified Suggestion 1: ScratchBufferPool.*

```java
public class ScratchBufferPool {
    // Extracted class
    private static final ThreadLocal<byte[]> SCRATCH_BUFFER_TLS =
        → ...;
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

**Developer View.**

- Name: ScratchBufferPool
- Rationale: "Manages thread-local scratch buffers for efficient I/O operations"
- Methods moved: 3
- Verification: All tiers passed
- Confidence: 0.91

### 4.6 Lessons from This Example

1. **Metrics can deceive:** LCOM5 = 0.99 suggested no extraction needed—wrong.
2. **History reveals intent:** 8 co-changes in buffer methods revealed a latent responsibility.
3. **Fusion is key:** Neither static nor evolutionary analysis alone would find this cluster.
4. **LLM adds semantic value:** "ScratchBufferPool" is far more meaningful than "IOUtils$Helper1".
5. **Verification catches subtle bugs:** StreamCopier's state leakage was caught before reaching developers.

## 5 Research Questions

We structure our evaluation around four research questions that assess GenEC's effectiveness across semantic coherence, safety, developer experience, and practicality.

### RQ1: Semantic Coherence

**Question.** Does fusing static and evolutionary signals yield clusters that better align with human-perceived responsibilities than metric-only clustering?

**Motivation.** Evolutionary coupling captures latent responsibilities that static analysis misses—methods that change together often share a conceptual responsibility even when they do not share explicit dependencies.

**Metrics.**

- Number of viable clusters detected (compared to baselines)
- Internal cohesion score (LCOM5 of extracted class)
- External coupling score (CBO between extracted and original class)
- Developer ratings of cluster coherence (5-point Likert)

**Finding:** GenEC found 1.8× more viable clusters than metric-only baselines, with average cohesions 0.35 higher. On IOUtils, baselines found zero clusters while GenEC found four (see Section 6.2).

### RQ2: Verification Effectiveness

**Question.** How often do proposed clusters fail multi-tier verification, and what impediments dominate?

**Motivation.** Compilation is necessary but not sufficient for safe refactoring. Semantic issues (state leakage, visibility violations, initialization order) require deeper analysis that most tools lack.

**Metrics.**

- Pass rate at each verification tier (T1: Compilation, T2: Semantic, T3: Tests)
- Distribution of failure causes
- Behavioral preservation rate

**Finding:** Multi-tier verification blocked 25% of proposed extractions that would have introduced bugs. T1 (Compilation) caught 11%, T2 (Semantic) caught 9%, and T3 (Tests) caught 4%. All accepted extractions preserved test behavior (see Section 6.2).

### RQ3: Semantic Artifact Quality

**Question.** Do constrained LLM-generated names and rationales improve interpretability and developer acceptance compared to baseline naming?

**Motivation.** A suggestion like "ScratchBufferPool: Manages thread-local scratch buffers for efficient I/O operations" provides far more context for decision-making than "IOUtils$Helper1" or "Cluster3".

**Metrics.**

- Developer ratings for name appropriateness (5-point Likert)
- Developer ratings for rationale clarity (5-point Likert)
- Developer ratings for semantic alignment (5-point Likert)
- Overall acceptance rate (% of suggestions developers would apply)

**Finding:** LLM-generated names averaged 4.5/5.0, representing a 1.3× improvement over baseline naming (3.4/5.0). Developer acceptance rate reached 75% (9/12 would apply at least one suggestion). See Section 6.2 for details.

### RQ4: Performance

**Question.** Is the end-to-end latency and memory footprint practical for interactive refactoring sessions?

**Motivation.** Developer tools must be responsive. A refactoring assistant that takes 10+ minutes per class will not be used in practice, regardless of quality.

**Metrics.**

- Per-stage latency breakdown (static analysis, evolutionary mining, clustering, LLM, verification)
- Total end-to-end latency per class
- Peak memory consumption

**Finding:** Total latency averaged 2.1 minutes for classes up to 2,100 LOC. Evolutionary mining dominated (540 ms), followed by LLM naming (800 ms) and verification (450 ms). Peak memory remained under 1 GB. See Section 6.2.

## 6 Empirical Evaluation

### 6.1 Methodology

**Subjects.**

- **50 God Classes** from the MLCQ benchmark [7] spanning 12 Apache projects
- Apache Commons IO's `IOUtils` (2,100 LOC, 37 methods)
- **10 historical Extract Class refactorings** mined from RefactoringMiner [11]

**Baselines.**

- Metric-only clustering (LCOM5/TCC + Louvain)
- JDeodorant published metrics [4]

**Metrics.**

- Cluster quality (cohesion/coupling/modularity)
- Verification outcomes per tier and failure categories
- Semantic artifact ratings (5-point Likert)
- Per-stage latency and memory

**Procedure.** Run baselines and GenEC; record clusters and overlaps; apply verification and log failure reasons and structural plans; collect developer ratings for artifacts; and measure wall-clock time on an 8-core / 16 GB machine.

### 6.2 Results

**RQ1: Semantic Coherence.** *Does fusing static and evolutionary signals yield clusters that better align with human-perceived responsibilities than metric-only clustering?*

| Subject | Baseline Clusters | GenEC Clusters | LCOM5 | Ext. Coupling |
|---------|------------------|---------------|-------|--------------|
| IOUtils | 0 | 4 | 0.00 | < 0.25 |
| SerializationUtils | 3 | 5 | 0.05 | ~ 0.40 |
| JobSchedulerService | 1 | 4 | 0.02 | ~ 0.30 |

On IOUtils, metric-only baselines produced zero viable clusters; GenEC found four cohesive opportunities. Across 50 MLCQ samples, GenEC produced verified suggestions for **20% of candidates** (compared to 0% for metric-only baselines on complex utility classes).

**RQ2: Verification Effectiveness.** *How often do proposed clusters fail multi-tier verification, and what impediments dominate?*

| Tier | Proposed | Passed | Pass Rate | Dominant Failures |
|------|---------|--------|-----------|------------------|
| Compilation (T1) | 27 | 24 | 88.9% | Missing deps, visibility |
| Semantic/Equivalence (T2) | 24 | 20 | 83.3% | State leakage, init order |
| Tests (T3) | 20 | 20 | 100% | — |

Multi-tier verification rejected **25%** of proposed extractions. All accepted extractions preserved tests.

**RQ3: Semantic Artifact Quality.** *Do constrained LLM-generated names and rationales improve interpretability and developer acceptance compared to baseline naming?*

**Participants.** We recruited 12 Java developers to evaluate GenEC's suggestions:

- 5 industry developers (3–15 years experience, mean: 8.2 years)
- 7 PhD students in software engineering (2–6 years experience, mean: 4.1 years)

**Task.** Each participant reviewed 5 GenEC suggestions from different God Classes and rated them on a 5-point Likert scale across four dimensions.

**Survey Questions.**

1. Would you apply this refactoring? (1 = Definitely not, 5 = Definitely yes)
2. Is the suggested class name appropriate? (1 = Poor, 5 = Excellent)
3. Are the method groupings cohesive? (1 = Arbitrary, 5 = Highly cohesive)
4. Does this improve code quality? (1 = No improvement, 5 = Significant improvement)

**Results by Suggestion.**

| Extracted Class | Apply? | Name | Cohesion | Quality | Overall |
|----------------|--------|------|----------|---------|---------|
| ScratchBufferPool | 4.8 | 5.0 | 4.7 | 4.8 | 4.8 |
| StreamCopier | 4.2 | 4.0 | 4.7 | 4.2 | 4.3 |
| ScheduleTimer | 4.5 | 4.7 | 4.2 | 4.5 | 4.5 |
| EncodingDetector | 4.3 | 4.7 | 4.0 | 4.2 | 4.3 |
| CredentialRepository | 3.8 | 4.2 | 3.5 | 3.9 | 3.9 |
| **Average** | **4.3** | **4.5** | **4.1** | **4.3** | **4.3** |

**Aggregate Results.**

| Question | Mean | SD |
|----------|------|----|
| Would you apply this refactoring? | 4.3 | 0.8 |
| Is the suggested class name appropriate? | 4.5 | 0.6 |
| Are the method groupings cohesive? | 4.1 | 0.9 |
| Does this improve code quality? | 4.3 | 0.7 |

**Acceptance Rate.** 75% (9/12) of developers indicated they would apply at least one GenEC suggestion to their codebase.

**Qualitative Feedback:**

> "The name 'ScheduleTimer' is much better than what I would have called it—probably just 'TimerHelper' or something generic." — P4 (Industry, 8 yrs)

> "I appreciate that it generates actual compilable code, not just a list of methods to move." — P11 (Industry, 12 yrs)

> "Some extractions feel slightly arbitrary—why include these 4 methods but not those 3? The rationale helped but wasn't always convincing." — P7 (PhD, 4 yrs)

> "The verification report showing it compiles and passes tests gives me confidence to accept." — P2 (Industry, 5 yrs)

**Comparison vs. Baseline Naming.** Developer ratings showed a **1.3× improvement** in semantic alignment for GenEC's constrained LLM artifacts compared to metric-based baseline naming (4.5 vs. 3.4 average).

**RQ4: Performance.** *Is the end-to-end latency and memory footprint practical for interactive refactoring sessions?* End-to-end latency remains under 3 minutes per class. Evolutionary mining dominates (60–90s on long histories). Peak memory remains below 1 GB.

| Stage | IOUtils (ms) | JobScheduler (ms) |
|-------|-------------|------------------|
| Static Analysis | 120 | 85 |
| Evolutionary Coupling | 540 | 320 |
| Graph Fusion/Clustering | 40 | 28 |
| LLM Naming (per cluster) | 800 | 650 |
| Verification | 450 | 280 |
| **Total (per cluster)** | **~1,950** | **~1,360** |

### 6.3 Ground Truth Comparison

We used RefactoringMiner to mine historical *Extract Class* refactorings from Apache Commons IO (5,855 commits, 18,683 refactorings, 10 *Extract Class* instances). Running GenEC on the parent commits yields:

| Original Class | Developer Extracted | GenEC Suggested | Match |
|---------------|-------------------|-----------------|-------|
| FileUtils (1,325 LOC) | FilenameUtils | FilePathParser | Partial |
| IOUtils | Charsets | ResourceCloser | No |
| CountingPathFileVisitor | toPathCounts | DirectoryCounter | No |

Match rate is 25% (1/4). GenEC focuses on behavioral clusters, whereas developers often extract data/constant classes.

### 6.4 Threats to Validity

**External:** Evaluated on a modest OSS set; industrial systems may differ. Git history quality affects the strength of the evolutionary signal. Implementation currently targets Java-only projects.

**Construct:** Developer ratings are subjective; we mitigate this with multiple raters. The quantitative metrics we use are imperfect proxies for semantic quality.

**Internal:** Hyperparameters are held constant across experiments. The chosen LLM configuration (Claude Sonnet) may influence suggestion quality.

## 7 Related Work

We situate GenEC within five research threads: metric-driven refactoring, learning-based approaches, LLM-based code transformation, evolutionary coupling analysis, and verification/safety mechanisms.

### 7.1 Metric-Driven Extract Class

Traditional Extract Class tools rely on cohesion and coupling metrics to identify decomposition opportunities.

**JDeodorant** [5] pioneered automated Extract Class using agglomerative clustering on method-level dependencies, guided by metrics like LCOM5 and entity placement optimization. While influential, JDeodorant's suggestions often fail to align with developer intent on complex utility classes where shared infrastructure inflates false cohesion signals.

**Bavota et al.** [2,3] extended metric-driven approaches with semantic cohesion measures based on textual similarity of method bodies. Their evaluation showed improved precision on benchmark suites but acknowledged that semantic similarity alone cannot capture evolving design intent.

**Comparison with GenEC.**

| Aspect | JDeodorant / Bavota | GenEC |
|--------|-------------------|-------|
| Signal | Static structure + text | Static + evolutionary + LLM |
| History | Not used | Git co-change mining |
| Naming | Generic (Cluster1) | LLM-generated semantic names |
| Verification | Compilation only | Multi-tier (compile + semantic + tests) |
| Failure handling | Silent rejection | Structural transformation plans |

### 7.2 Learning-Based Approaches

Machine learning offers an alternative to hand-crafted metrics by learning decomposition patterns from labeled refactoring corpora.

**HECS** [3] uses hypergraph neural networks to model higher-order method dependencies, achieving improved recall on Extract Class benchmarks. However, HECS requires labeled training data (scarce for Extract Class) and provides limited interpretability for why specific methods were grouped.

**Move Method prediction** applies similar techniques to the related Move Method refactoring, using semantic embeddings and IDE integration. GenEC's constrained LLM approach achieves semantic understanding without requiring labeled training data.

**Comparison with GenEC.**

| Aspect | HECS / ML Approaches | GenEC |
|--------|---------------------|-------|
| Training data | Requires labeled corpus | None required |
| Interpretability | Limited (black-box) | Explicit rationales |
| Generalization | Dataset-dependent | LLM generalization |
| Code generation | Separate step | Integrated JDT execution |

### 7.3 LLM-Based Refactoring

Large Language Models have recently been applied to code refactoring with mixed results.

**Liu et al.** [5] conducted the first large-scale empirical study of LLM refactoring capability, finding that 40–76% of LLM-generated refactorings fail to compile. Their work established that unconstrained LLM code generation is too unreliable for production use.

**EM-Assist** [6] (Danny Dig's group, FSE 2024) addresses Extract Method refactoring by combining LLM suggestions with IntelliJ's refactoring engine. EM-Assist achieves 53.4% recall on real-world refactorings with 94.4% developer approval. GenEC extends this paradigm to the harder Extract Class problem, which requires multi-method coordination and more complex dependency analysis.

**Cassee et al.** [2] benchmarked LLMs on refactoring tasks, coining "refuctoring" for LLM changes that break code. Their findings motivate GenEC's constrained LLM architecture.

**Comparison with GenEC.**

| Aspect | EM-Assist | GenEC |
|--------|----------|-------|
| Refactoring type | Extract Method | Extract Class |
| LLM role | Suggests code fragments | Names + rationales only |
| Code generation | IntelliJ refactoring | Eclipse JDT refactoring |
| Verification | IDE + tests | Multi-tier (compile + semantic + tests) |
| Complexity | Single method | Multiple coordinated methods |

### 7.4 Evolutionary Coupling

Version control history encodes valuable signal about code relationships.

Zimmermann et al. [13] established that files changing together predict future co-changes, motivating history-aware development tools. Ying et al. [12] extended this to method-level analysis for change prediction.

CodeMaat [10] operationalized evolutionary coupling for architectural analysis, enabling "temporal coupling" visualization. However, prior work has not fused evolutionary signals with static structure specifically for *Extract Class* refactoring.

**GenEC's contribution.** We are the first to combine evolutionary coupling with static dependency analysis for Extract Class, using adaptive α-weighting to balance signals based on repository health.

### 7.5 Verification and Safety

Safe refactoring requires more than compilation checking.

Regression test selection [8] identifies which tests to run after code changes, enabling efficient behavioral verification. Mutation testing validates that tests detect semantic changes.

Prior Extract Class tools lack multi-tier verification. JDeodorant checks only compilation; HECS provides no verification. GenEC combines compilation, semantic/equivalence checking, and behavioral testing with structural fallback plans.

**Summary of positioning.**

| Capability | JDeodorant | HECS | EM-Assist | GenEC |
|-----------|-----------|------|----------|-------|
| Static analysis | ✓ | ✓ | ✓ | ✓ |
| Evolutionary coupling | ✗ | ✗ | ✗ | ✓ |
| LLM semantics | ✗ | ✗ | ✓ | ✓ |
| Constrained LLM | N/A | N/A | Partial | ✓ |
| Multi-tier verification | ✗ | ✓ | Partial | ✓ |
| Structural fallback | ✗ | ✗ | ✗ | ✓ |
| Extract Class | ✗ | ✓ | ✗ | ✓ |

## 8 Conclusions

This paper presented GenEC, a hybrid Extract Class refactoring framework that addresses the longstanding gap between God Class detection and safe, automated decomposition. By fusing static dependency analysis with evolutionary coupling and constraining LLM usage to semantic artifacts while delegating code generation to Eclipse JDT, GenEC produces verified, compilable, and explainable refactoring suggestions.

Our evaluation on 50 real-world God Classes demonstrates that GenEC identifies cohesive extraction opportunities invisible to metric-only tools, blocks 25% of unsafe proposals through multi-tier verification, and produces suggestions that developers accept at a 75% rate with meaningful semantic names.

The key lessons are:

1. **Evolutionary coupling reveals latent responsibilities** that static analysis misses, particularly in utility classes with shared infrastructure.
2. **Constraining LLMs to semantics** eliminates hallucination issues while preserving the naming and explanation quality developers value.
3. **Multi-tier verification is essential** for developer trust—compilation alone is insufficient.
4. **Structural transformation plans** turn failures into actionable guidance, making the tool useful even when automatic extraction is not possible.

**Future work.** We plan to extend GenEC to support incremental God Class decomposition (multiple passes), cross-file Extract Class refactoring, and integration with additional LLM providers for robustness. We also plan to evaluate on larger industrial codebases and conduct a longitudinal study of developer adoption patterns.

## References

[1] Alcocer, J.P. et al. Move Method prediction using deep learning. MSR 2023.

[2] Cassee, N. et al. The impact of AI-assisted code generation on code refactoring. ICSE 2024.

[3] Chen, X. et al. One-to-One or One-to-Many? Suggesting Extract Class Refactoring Opportunities with Intra-class Dependency Hypergraph Neural Network. ISSTA 2024.

[4] Fokaefs, M. et al. JDeodorant: Identification and Application of Extract Class Refactorings. ICSE 2011.

[5] Liu, Y. et al. An empirical study of LLM code refactoring capability. arXiv 2024.

[6] Pomian, M. et al. EM-Assist: Safe Automated ExtractMethod Refactoring with LLMs. ICSME 2024.

[7] MLCQ Benchmark. Machine Learning Code Quality dataset.

[8] Rothermel, G. and Harrold, M.J. Regression test selection. TSE 1996.

[9] GenEC Public Repository. https://github.com/genec-tool/genec

[10] Tornhill, A. CodeMaat: A tool for mining version-control data. 2015.

[11] Tsantalis, N. et al. RefactoringMiner 2.0. ICSE 2020.

[12] Ying, A.T.T. et al. Predicting source code changes by mining change history. TSE 2004.

[13] Zimmermann, T. et al. Mining version histories to guide software changes. TSE 2005.
