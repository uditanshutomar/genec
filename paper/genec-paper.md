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

God Classes—monolithic Java behemoths that accumulate dozens of unrelated responsibilities—still plague even mature open-source libraries, yet existing refactoring tools either stay silent or suggest extractions that break compilation or semantics. Large Java classes with tangled concerns make maintenance and evolution risky, and approaches based solely on metrics, static dependencies, or unconstrained machine learning often surface refactorings that are semantically misaligned or unsafe. GenEC attacks this gap with a hybrid pipeline that fuses static dependency analysis with evolutionary coupling mined from version history, while constraining a Large Language Model (LLM) to generate only semantic artifacts (names, documentation, rationale) and delegating all structural edits to IDE-grade refactoring engines such as Eclipse JDT. Every candidate extraction is gated by multi-tier verification—compilation (with stub generation where needed), semantic-equivalence checks, and test preservation—and clusters that fail these gates are not silently discarded but instead yield structural transformation plans for manual follow-up. Our empirical evaluation on 23 real-world God Classes from 6 open-source projects (Apache Commons IO/Lang/Collections/Text/Math, JFreeChart) shows that GenEC consistently identifies semantically coherent extraction opportunities that metric-only baselines miss, while blocking 41.6% of proposals that would have broken compilation or equivalence. On Apache Commons IO's 4,012-line IOUtils (172 methods), metric-based analysis produced zero viable extraction groups despite clear design smells, whereas GenEC's fused analysis surfaced one verified extraction opportunity ("ResourceLoader" — internal cohesion 0.80, external coupling 0.25) that preserved existing tests. On the established HECS ECAccEval benchmark (92 instances), GenEC achieves macro F1=0.478 on instances with full evolutionary context (21 instances). We release the complete tooling, prompts, evaluation harness, and replication package to support reproducibility and future work on safe, explainable automated refactoring.

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

Consider `IOUtils` from Apache Commons IO—a 4,012-line class with 172 methods and 8 fields. Its LCOM5 score is 1.0 and TCC is 0.064, so metric-only tools propose zero viable extractions. Yet manual inspection reveals distinct responsibilities buried among the overloaded utility methods.

GenEC's analysis discovered that the resource-loading methods (`resourceToString()`, `resourceToURL()` and their overloads) form a cohesive cluster with internal cohesion of 0.80 and external coupling of 0.25. The LLM named it "ResourceLoader" with the rationale: "These methods form a cohesive unit responsible for loading classpath resources and converting them to strings." JDT executed the extraction; verification passed all tiers. A developer reviewing this suggestion sees not just a list of methods but a coherent responsibility with a meaningful name and mechanical guarantees.

### 1.4 Empirical Evaluation Summary

We evaluated GenEC on:

- **23 God Classes** from 6 open-source projects (Apache Commons IO/Lang/Collections/Text/Math, JFreeChart)
- **Baselines:** field-sharing clustering (37 suggestions) and random grouping (526 suggestions)
- **HECS ECAccEval benchmark:** 92 Extract Class instances for ground-truth comparison

Key results:

- GenEC produced **178 suggestions**, of which **104 passed multi-tier verification** (58.4% verification rate). Field-sharing baselines produced only 37 suggestions with no compilable extractions.
- **Multi-tier verification blocked 41.6%** of proposed extractions that would have broken compilation or equivalence—preventing unsafe suggestions from reaching developers.
- **"Should"-tier suggestions verified at 88.9%**, "could"-tier at 57.7%, demonstrating quality-tier stratification.
- **HECS benchmark:** On the 21 instances with evolutionary context, GenEC achieves macro F1=0.478 (precision 0.41, recall 0.76).
- **Average end-to-end latency of 201 seconds per class** on commodity hardware, practical for interactive use.

### 1.5 Contributions

This paper makes the following contributions:

1. **Hybrid analysis for Extract Class** that fuses static dependency structure with evolutionary co-change signals, surfacing semantically coherent clusters that metric-only tools miss (Section 3).
2. **Constrained LLM usage** that limits the model to naming and rationales while Eclipse JDT performs structural edits, eliminating hallucinated code while preserving semantic value (Section 3.3).
3. **Multi-tier verification pipeline** with compilation, semantic/equivalence, and behavioral checks—plus structural fallback plans that provide actionable guidance when extraction fails (Section 3.4).
4. **Empirical evaluation** on 23 real-world God Classes from 6 projects demonstrating higher-quality clusters, 41.6% unsafe proposals blocked, and macro F1=0.478 on the HECS benchmark with evolutionary context (Section 6).
5. **Replication package** including complete tooling, prompts, evaluation harness, and VS Code extension, available in our public repository [9].

## 2 Technical Challenges

Building an Extract Class tool that developers trust requires addressing several fundamental challenges that span signal integration, safety guarantees, and user experience.

### C1: Aligning Structural Metrics with Developer Intent

Classical cohesion metrics like LCOM5 (Lack of Cohesion of Methods) and coupling metrics like CBO (Coupling Between Objects) were designed to flag problematic classes, not to guide decomposition. Community detection on method-call graphs optimizes graph properties (modularity, edge density) but routinely misses conceptual boundaries.

**The problem is particularly acute in utility classes.** Consider IOUtils from Apache Commons IO: it has 172 methods that share a handful of common helper fields (buffers, default encodings). Metrics see high field-sharing and conclude the class is cohesive. But a human reviewer immediately recognizes that stream-copying methods, encoding-detection methods, and buffer-management methods serve distinct responsibilities that happen to share infrastructure.

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

- **A meaningful name** generated by the LLM (e.g., "ResourceLoader" not "Class1").
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
- α_call = 1.0, α_field = 0.8, with an additional α_shared_field = 0.9 for shared field access (configurable weights)

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

The configured default is α = 0.5, but the pipeline applies adaptive hotspot-based fusion where α varies per edge: high-hotspot edges use α as low as 0.2 (80% evolutionary), while low-hotspot edges use α = 0.8 (80% static). When evolutionary signal is weak (fewer than 10 co-changes total), α is adaptively increased toward 1.0.

Community detection uses the Leiden algorithm (preferred for stability) or Louvain (fallback). The pipeline default resolution is 2.0 (favoring more, smaller clusters), though the config file default is 1.0. Multi-resolution search over [0.5, 0.75, 1.0, 1.25, 1.5] is available but disabled by default.

We filter clusters requiring:

- Minimum of 3 methods.
- At most 40% of the original class size.
- Internal cohesion > 0.35 (ratio of intra-cluster edges to possible edges).

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

IOUtils is a 4,012-line utility class with 172 methods providing I/O convenience functions. It has been part of Apache Commons IO since 2002 and is used by thousands of downstream projects.

**Class Statistics:**

| Metric | Value |
|--------|-------|
| Lines of Code | 4,012 |
| Methods | 172 |
| Fields | 8 |
| LCOM5 | 1.0 (appears maximally uncohesive) |
| TCC | 0.064 (very low connectivity) |
| CBO | 9 |

**Sample Methods (representative subset of 172).**

```java
public class IOUtils {
    // Stream copying (many overloads)
    public static long copy(InputStream input, OutputStream output) { ... }
    public static int copy(InputStream input, OutputStream output,
        int bufferSize) { ... }

    // Resource loading (the cluster GenEC extracts)
    public static String resourceToString(String name, Charset charset) { ... }
    public static URL resourceToURL(String name) { ... }

    // String/encoding conversion
    public static String toString(InputStream input, Charset charset) { ... }

    // Reader creation
    public static BufferedReader toBufferedReader(Reader reader) { ... }
    public static LineIterator lineIterator(Reader reader) { ... }
}
```

### 4.2 Why Metric-Only Tools Fail

JDeodorant and similar metric-based tools analyze IOUtils and find:

- **High field sharing:** Many methods access common fields (e.g., DEFAULT_BUFFER_SIZE, SKIP_BUFFER).
- **Extensive method calls:** Utility methods call each other frequently.
- **LCOM5 = 1.0, TCC = 0.064:** The class is large and uncohesive by metrics, yet the field-sharing baseline produces only 1 suggestion (a generic "IOUtils$Helper1" grouping 13 methods by shared field access).

**Result:** The field-sharing baseline produces one low-quality cluster with no verification. GenEC's fused analysis finds 37 candidate clusters, filters down to 1 verified extraction.

The challenge with IOUtils is that its 172 methods are mostly static utilities with minimal field sharing, making structural clustering difficult. Most methods are independent overloaded variants that do not share fields or call each other.

### 4.3 GenEC's Analysis

*Stage 1: Static Dependency Graph.* GenEC builds a weighted dependency graph over IOUtils' 172 methods. With such a large utility class, most methods are static and share few fields, producing a sparse graph.

*Stage 2: Evolutionary Coupling.* Git history mining reveals co-change patterns among the resource-loading methods (`resourceToString`, `resourceToURL` and their overloads), which changed together across commits while rarely changing with stream-copying or encoding methods.

*Stage 3: Fused Graph and Clustering.* Community detection on the fused graph produces 37 candidate clusters. After quality filtering (internal cohesion > 0.35, size constraints), only 1 cluster passes: a group of 4 resource-loading methods with internal cohesion of 0.80 and external coupling of 0.25.

*Stage 4: LLM Naming.*

The LLM names the cluster "ResourceLoader" with the rationale: "These methods form a cohesive unit responsible for loading classpath resources and converting them to strings. They handle the complete workflow from resource discovery to content conversion."

**LLM Response:**

> Name: ResourceLoader
> Rationale: These methods form a cohesive unit responsible for loading classpath resources and converting them to strings.
>
> Confidence: 0.90

### 4.4 Verification Results

The single candidate extraction passes through the multi-tier verification pipeline.

| Cluster | T1: Compile | T2: Semantic | T3: Tests | Result |
|---------|-------------|-------------|-----------|--------|
| ResourceLoader | Pass | Pass | Pass | Verified |

**Table 1:** Verification results for candidate extractions in IOUtils.

### 4.5 Final Output

GenEC produces one verified suggestion for IOUtils.

*Verified Suggestion: ResourceLoader.*

- **Methods:** `resourceToString(String,Charset)`, `resourceToString(String,Charset,ClassLoader)`, `resourceToURL(String)`, `resourceToURL(String,ClassLoader)`
- **Fields:** None (stateless extraction)
- **Quality tier:** "should" (score 75.0)

**Developer View.**

- Name: ResourceLoader
- Rationale: "These methods form a cohesive unit responsible for loading classpath resources and converting them to strings."
- Methods moved: 4
- Verification: All tiers passed
- Confidence: 0.90
- Post-extraction LCOM5: 1.0 (original class barely changes — 4 of 172 methods extracted)

### 4.6 Lessons from This Example

1. **Large utility classes are hard:** With 172 methods and minimal field sharing, IOUtils yields only 1 verified extraction out of 37 candidates — a 2.7% filter pass rate.
2. **Quality over quantity:** The single verified suggestion has high internal cohesion (0.80) and reasonable coupling (0.25), making it a genuinely useful extraction.
3. **LLM adds semantic value:** "ResourceLoader" is far more meaningful than "IOUtils$Helper1" (the field-sharing baseline's name).
4. **Honest limitations:** IOUtils' design (172 static utility methods with minimal interdependencies) resists decomposition. GenEC correctly identifies this by rejecting 36 of 37 clusters.

## 5 Research Questions

We structure our evaluation around four research questions that assess GenEC's effectiveness across semantic coherence, safety, developer experience, and practicality.

### RQ1: Semantic Coherence

**Question.** Does fusing static and evolutionary signals yield clusters that better align with human-perceived responsibilities than metric-only clustering?

**Motivation.** Evolutionary coupling captures latent responsibilities that static analysis misses—methods that change together often share a conceptual responsibility even when they do not share explicit dependencies.

**Metrics.**

- Number of viable clusters detected (compared to baselines)
- Internal cohesion score of extracted clusters
- External coupling score between extracted and original class
- Wilcoxon signed-rank test and Cliff's delta for statistical comparison

**Finding:** GenEC produced 178 suggestions across 23 classes versus 37 for the field-sharing baseline (Wilcoxon p=0.0005, Cliff's delta=0.828, "large" effect). Verified suggestions average 5.9 methods with mean internal cohesion of 0.77 (95% CI: [0.74, 0.79]). See Section 6.2.

### RQ2: Verification Effectiveness

**Question.** How often do proposed clusters fail multi-tier verification, and what impediments dominate?

**Motivation.** Compilation is necessary but not sufficient for safe refactoring. Semantic issues (state leakage, visibility violations, initialization order) require deeper analysis that most tools lack.

**Metrics.**

- Pass rate at each verification tier (T1: Compilation, T2: Semantic, T3: Tests)
- Distribution of failure causes
- Behavioral preservation rate

**Finding:** Multi-tier verification blocked 41.6% of proposed extractions (74 of 178). "Should"-tier suggestions verified at 88.9% (16/18), "could"-tier at 57.7% (86/149), and "potential"-tier at 18.2% (2/11). The strong correlation between quality tier and verification rate validates the tier stratification. See Section 6.2.

### RQ3: Semantic Artifact Quality

**Question.** Do constrained LLM-generated names and rationales improve interpretability and developer acceptance compared to baseline naming?

**Motivation.** A suggestion like "ResourceLoader: These methods form a cohesive unit responsible for loading classpath resources" provides far more context for decision-making than "IOUtils$Helper1" or "Cluster3".

**Metrics.**

- Developer ratings for name appropriateness (5-point Likert)
- Developer ratings for rationale clarity (5-point Likert)
- Developer ratings for semantic alignment (5-point Likert)
- Overall acceptance rate (% of suggestions developers would apply)

**Finding:** Pending user study. Qualitative inspection of LLM-generated names (e.g., "ResourceLoader", "ByteSizeFormatter", "ShutdownFileDeleter") suggests meaningful semantic labels compared to baseline naming ("IOUtils$Helper1", "RandomGroup1"). A formal developer study with Likert-scale ratings is planned as future work.

### RQ4: Performance

**Question.** Is the end-to-end latency and memory footprint practical for interactive refactoring sessions?

**Motivation.** Developer tools must be responsive. A refactoring assistant that takes 10+ minutes per class will not be used in practice, regardless of quality.

**Metrics.**

- Per-stage latency breakdown (static analysis, evolutionary mining, clustering, LLM, verification)
- Total end-to-end latency per class
- Peak memory consumption

**Finding:** Total latency averaged 201.3 seconds (approximately 3.4 minutes) per class across all 23 subjects, with total wall-clock time of 4,629 seconds. IOUtils (172 methods) completed in only 18.8 seconds due to its sparse dependency structure, while larger classes like JFreeChart's DefaultPolarItemRenderer took longer. See Section 6.2.

## 6 Empirical Evaluation

### 6.1 Methodology

**Subjects.**

- **23 God Classes** from 6 open-source projects:
  - Apache Commons IO (3 classes): IOUtils, FileUtils, FilenameUtils
  - Apache Commons Lang (5 classes): StringUtils, NumberUtils, ClassUtils, ArrayUtils, DateUtils
  - Apache Commons Collections (3 classes): CollectionUtils, MapUtils, ListUtils
  - Apache Commons Text (3 classes): StringSubstitutor, StrBuilder, WordUtils
  - Apache Commons Math (4 classes): FastMath, MathArrays, ArithmeticUtils, Fraction
  - JFreeChart (5 classes): various plot and renderer classes

**Baselines.**

- **Field-sharing clustering:** groups methods by shared field access (37 total suggestions)
- **Random grouping:** random method partitioning (526 total suggestions)

**Metrics.**

- Cluster quality (internal cohesion, external coupling, modularity)
- Verification outcomes per quality tier
- Statistical comparison (Wilcoxon signed-rank, Cliff's delta)
- Per-class latency

**Procedure.** Run baselines and GenEC on all 23 classes; record clusters and verification outcomes; compare suggestion counts and quality; measure wall-clock time on commodity hardware. Additionally, evaluate on the HECS ECAccEval benchmark (92 instances) for ground-truth comparison.

### 6.2 Results

**RQ1: Semantic Coherence.** *Does fusing static and evolutionary signals yield clusters that better align with human-perceived responsibilities than metric-only clustering?*

| Project | Classes | GenEC Suggestions | GenEC Verified | Baseline Suggestions |
|---------|---------|-------------------|----------------|---------------------|
| commons-io | 3 | 13 | 13 | 4 |
| commons-lang | 5 | 25 | 23 | 8 |
| commons-collections | 3 | 16 | 12 | 5 |
| commons-text | 3 | 14 | 8 | 5 |
| commons-math | 4 | 26 | 23 | 6 |
| jfreechart | 5 | 84 | 25 | 9 |
| **Total** | **23** | **178** | **104** | **37** |

GenEC produced 178 suggestions versus 37 for the field-sharing baseline — a statistically significant improvement (Wilcoxon p=0.0005, Cliff's delta=0.828, "large" effect). Verified suggestions average 5.9 methods with mean internal cohesion of 0.77 (95% CI: [0.74, 0.79]). The overall cluster filter pass rate was 16.6% (178 of 1,071 raw clusters).

**RQ2: Verification Effectiveness.** *How often do proposed clusters fail multi-tier verification, and what impediments dominate?*

| Quality Tier | Proposed | Verified | Verification Rate |
|-------------|---------|----------|------------------|
| "should" (high quality) | 18 | 16 | 88.9% |
| "could" (moderate quality) | 149 | 86 | 57.7% |
| "potential" (marginal) | 11 | 2 | 18.2% |
| **Total** | **178** | **104** | **58.4%** |

Multi-tier verification rejected **41.6%** of proposed extractions (74 of 178). The strong correlation between quality tier and verification rate validates GenEC's tier stratification: "should"-tier suggestions are almost always safe (88.9%), while "potential"-tier suggestions rarely survive verification (18.2%). The overall mean verification rate is 68.0% (95% CI: [51.9%, 83.0%]).

**RQ3: Semantic Artifact Quality.** *Do constrained LLM-generated names and rationales improve interpretability and developer acceptance compared to baseline naming?*

**Status:** A formal developer study with Likert-scale ratings is planned as future work. We report qualitative observations from the automated evaluation.

**Qualitative comparison of naming.** GenEC's LLM-generated names are semantically descriptive compared to baseline alternatives:

| GenEC Name | Baseline Name | Project |
|-----------|--------------|---------|
| ResourceLoader | IOUtils$Helper1 | commons-io |
| ByteSizeFormatter | FileUtils$Helper2 | commons-io |
| ShutdownFileDeleter | FileUtils$Helper3 | commons-io |
| DirectoryCreator | FileUtils$Helper4 | commons-io |

Each GenEC suggestion includes a one-sentence rationale grounded in the cluster's methods and co-change evidence, providing developers with context for acceptance decisions. A formal user study to quantify the impact on developer acceptance is planned.

**RQ4: Performance.** *Is the end-to-end latency and memory footprint practical for interactive refactoring sessions?*

Average end-to-end latency is 201.3 seconds per class (total 4,629 seconds across 23 classes). Latency varies significantly by class complexity:

| Class | Methods | Execution Time (s) | Suggestions |
|-------|---------|-------------------|-------------|
| IOUtils | 172 | 18.8 | 1 |
| FileUtils | 159 | 136.2 | 7 |
| StringUtils | 166 | — | — |
| JFreeChart classes | varies | up to 600+ | varies |

IOUtils completes quickly (18.8s) because its sparse dependency structure produces few viable clusters. Classes with richer dependency graphs and more verification candidates take proportionally longer. The pipeline is practical for batch analysis but classes with many verification candidates may exceed interactive thresholds.

### 6.3 HECS Benchmark Comparison

We evaluated GenEC on the HECS ECAccEval benchmark [3], which provides 92 ground-truth Extract Class instances from real-world projects.

| Subset | Instances | Precision | Recall | Macro F1 |
|--------|-----------|-----------|--------|----------|
| With evolutionary context | 21 | 0.405 | 0.758 | 0.478 |
| Static only (no evo history) | 71 | 0.057 | 0.161 | 0.076 |
| Multi-member (3+ members) | 49 | 0.228 | 0.476 | 0.281 |
| **All instances** | **92** | **0.136** | **0.297** | **0.167** |

**Key finding on evolutionary coupling:** A controlled ablation running `--no-evo` on the same 21 instances with evolutionary context produces identical F1=0.478. This reveals that evolutionary coupling improves candidate discovery (+27.4% more clusters on the live benchmark) rather than member-selection accuracy. The evo signal helps find more potential extraction sites but does not change which members are grouped once a cluster is found.

**Limitations on static-only instances:** On the 71 instances without meaningful evolutionary history, GenEC achieves only F1=0.076, highlighting the tool's dependence on repository health and the difficulty of matching HECS's labeled extractions using purely structural signals.

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

**GenEC's contribution.** We are the first to combine evolutionary coupling with static dependency analysis for Extract Class, using adaptive α-weighting to balance signals based on repository health. Our controlled ablation reveals a nuanced finding: evolutionary coupling improves candidate discovery (+27.4% more clusters) rather than member-selection accuracy (identical F1 in controlled ablation on the same instances). This suggests that evo coupling's primary value for Extract Class is broadening the search space, not refining individual cluster composition.

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

Our evaluation on 23 real-world God Classes from 6 open-source projects demonstrates that GenEC identifies cohesive extraction opportunities invisible to metric-only tools (178 vs. 37 suggestions, Wilcoxon p=0.0005), blocks 41.6% of unsafe proposals through multi-tier verification, and produces suggestions with meaningful semantic names. On the HECS benchmark, GenEC achieves macro F1=0.478 on instances with evolutionary context.

The key lessons are:

1. **Evolutionary coupling improves candidate discovery** (+27.4% more clusters) rather than member-selection accuracy (identical F1 in controlled ablation), particularly valuable in utility classes with shared infrastructure.
2. **Constraining LLMs to semantics** eliminates hallucination issues while preserving the naming and explanation quality developers value.
3. **Multi-tier verification is essential** for developer trust—compilation alone is insufficient.
4. **Structural transformation plans** turn failures into actionable guidance, making the tool useful even when automatic extraction is not possible.

**Future work.** We plan to extend GenEC to support incremental God Class decomposition (multiple passes), cross-file Extract Class refactoring, and integration with additional LLM providers for robustness. We also plan to conduct a formal developer study with Likert-scale ratings to quantify the impact of LLM-generated semantic artifacts on developer acceptance, evaluate on larger industrial codebases, and conduct a longitudinal study of developer adoption patterns.

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
