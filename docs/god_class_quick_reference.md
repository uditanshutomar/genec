# God Class & Extract Class: Quick Reference

**Quick lookup guide for developers and researchers**
**Date:** 2025-12-05

---

## God Class Detection - Quick Metrics

### Universal Red Flags
```
✗ LOC > 400
✗ WMC > 47
✗ LCOM5 > 0.6
✗ TCC < 0.33
✗ Methods > 25
✗ Fields > 15
```

### PMD God Class Rule
```
WMC >= 47 AND ATFD > 5 AND TCC < 1/3
```

### Project-Specific Ranges (Research Square 2025)
```
LOC:  104-407
WMC:  18-72
CBO:  8-69
RFC:  38-95
```

---

## Extract Class - Quick Decision Tree

```
Does the class have > 300 LOC?
├─ No → Probably okay, check other metrics
└─ Yes → Potential God Class
    │
    ├─ Can you identify 2+ distinct responsibilities?
    │  ├─ No → May not need extraction
    │  └─ Yes → Good extraction candidate
    │      │
    │      ├─ Are there data clumps (3+ fields always used together)?
    │      │  └─ Yes → Extract data object (HIGH PRIORITY)
    │      │
    │      ├─ Do methods access different field subsets?
    │      │  └─ Yes → Extract by field grouping
    │      │
    │      ├─ Is there a service/calculator/processor responsibility?
    │      │  └─ Yes → Extract service class
    │      │
    │      └─ Are there polymorphic conditionals (if/switch on type)?
    │         └─ Yes → Consider Strategy pattern extraction
```

---

## Cohesion Metrics - Quick Guide

### LCOM5 (Lack of Cohesion 5)

**Formula:**
```
LCOM5 = (m - Σ(mA)/a) / (m - 1)

Where:
  m = number of methods
  a = number of fields
  mA = methods accessing each field
```

**Interpretation:**
```
0.0 - 0.3  ✓ High cohesion (excellent)
0.3 - 0.5  ✓ Moderate cohesion (good)
0.5 - 0.7  ⚠ Low cohesion (consider refactoring)
0.7 - 1.0  ✗ Very low cohesion (God Class)
```

### TCC (Tight Class Cohesion)

**Formula:**
```
TCC = NDC / NP

Where:
  NDC = directly connected method pairs
  NP = max possible connections = m(m-1)/2

Two methods are connected if they:
  - Access same field, OR
  - One calls the other
```

**Interpretation:**
```
0.7 - 1.0  ✓ High cohesion
0.5 - 0.7  ✓ Moderate cohesion
0.3 - 0.5  ⚠ Low cohesion
0.0 - 0.3  ✗ Very low cohesion (God Class)
```

---

## Coupling Metrics - Quick Guide

### CBO (Coupling Between Objects)

**Count classes coupled via:**
- Field types
- Method parameters
- Return types
- Method calls

**Thresholds:**
```
0 - 5   ✓ Low coupling (excellent)
6 - 10  ✓ Moderate coupling (acceptable)
11 - 15 ⚠ High coupling (review design)
16+     ✗ Very high coupling (God Class)
```

### Instability (I)

**Formula:**
```
I = Ce / (Ca + Ce)

Where:
  Ce = Efferent coupling (outgoing)
  Ca = Afferent coupling (incoming)
```

**Interpretation:**
```
0.0 - 0.3  Stable (depends on many)
0.3 - 0.7  Balanced
0.7 - 1.0  Unstable (depends on few, many depend on it)
```

---

## Extraction Patterns - Quick Lookup

### 1. Data Clump Extraction

**Symptoms:**
```java
private String customerName;
private String customerEmail;
private String customerPhone;
```

**Solution:**
```java
class Customer {
    String name, email, phone;
}
```

**Priority:** HIGH | **Difficulty:** Easy

---

### 2. Feature Envy Extraction

**Symptoms:**
```java
// In class A
public void process() {
    b.getData1();
    b.getData2();
    b.getData3();
    // Uses b more than own fields
}
```

**Solution:** Move method to class B

**Priority:** HIGH | **Difficulty:** Medium

---

### 3. Service Extraction

**Symptoms:**
```java
public double calculateTotal() { ... }
public double calculateTax() { ... }
public double applyDiscount() { ... }
```

**Solution:**
```java
class PriceCalculator {
    double calculateTotal(...) { ... }
    double calculateTax(...) { ... }
    double applyDiscount(...) { ... }
}
```

**Priority:** MEDIUM | **Difficulty:** Medium

---

### 4. Strategy Extraction

**Symptoms:**
```java
if (type == "A") { ... }
else if (type == "B") { ... }
```

**Solution:**
```java
interface Strategy { void execute(); }
class StrategyA implements Strategy { ... }
class StrategyB implements Strategy { ... }
```

**Priority:** LOW | **Difficulty:** Hard

---

## Evaluation Metrics - Quick Reference

### Precision & Recall

```
Precision = TP / (TP + FP)
  → How many proposed extractions are correct?
  → Target: > 70% (excellent: > 85%)

Recall = TP / (TP + FN)
  → How many correct extractions were found?
  → Target: > 60% (excellent: > 80%)

F1-Score = 2 × (P × R) / (P + R)
  → Balanced measure
  → Target: > 65% (excellent: > 80%)
```

### Quality Indicators

```
✓ Good Extraction:
  • LCOM5 < 0.3 (both classes)
  • TCC > 0.7 (both classes)
  • CBO decreased (original)
  • Meaningful class name
  • Clear single responsibility
  • Low coupling between extractions

✗ Bad Extraction:
  • LCOM5 > 0.7 (extracted class)
  • High coupling between classes
  • Generic name (Utils, Helper, Manager)
  • Mixed responsibilities
  • Over-fragmentation (< 30 LOC)
```

---

## Test Case Sizes - Quick Guide

| Difficulty | LOC | Methods | Fields | Groups | Example |
|------------|-----|---------|--------|--------|---------|
| **Easy** | 150-250 | 10-15 | 6-10 | 2-3 | Library book manager with clear data clumps |
| **Medium** | 250-450 | 15-25 | 10-15 | 3-4 | Shopping cart with mixed concerns |
| **Hard** | 450-700 | 25-40 | 15-25 | 4-6 | User account with security, permissions, billing |
| **Very Hard** | 700+ | 40+ | 25+ | 5+ | Real enterprise class with complex dependencies |

---

## Common Pitfalls - Quick Checklist

### Don't Extract If:
- [ ] Class has single, clear responsibility
- [ ] LOC < 200 and cohesion is good
- [ ] Methods are tightly related
- [ ] Extraction would create tight coupling
- [ ] It's a legitimate utility class (domain-focused)

### Do Extract If:
- [ ] Multiple distinct responsibilities
- [ ] Clear data clumps (3+ related fields)
- [ ] Low cohesion (LCOM5 > 0.6)
- [ ] Feature envy detected
- [ ] Service logic mixed with data
- [ ] Conditional logic based on type

### Red Flags After Extraction:
- [ ] Circular dependencies
- [ ] Generic names (ExtractedClass1, Helper)
- [ ] High coupling between extractions
- [ ] Classes < 30 LOC (over-fragmented)
- [ ] Many parameters passed between classes
- [ ] Broken encapsulation (too many getters)

---

## Naming Conventions - Quick Guide

### Good Class Names

```
✓ Customer (not CustomerData, CustomerInfo)
✓ PriceCalculator (not Calculator, PriceUtils)
✓ PaymentProcessor (not PaymentHelper)
✓ ShippingManager (context-specific Manager)
✓ OrderValidator (specific purpose)
```

### Bad Class Names

```
✗ ExtractedClass1 (generic + numbered)
✗ Helper (too generic)
✗ Utils (vague)
✗ Manager (without context)
✗ Data, Info, Stuff (meaningless)
```

### Naming Patterns by Type

| Type | Pattern | Example |
|------|---------|---------|
| **Data Object** | Noun | Customer, Order, Product |
| **Service** | Noun + Verb-er | PriceCalculator, OrderProcessor |
| **Manager** | Noun + Manager | SessionManager, CacheManager |
| **Strategy** | Noun + Strategy | PaymentStrategy, SortingStrategy |
| **Factory** | Noun + Factory | CustomerFactory, ReportFactory |
| **Validator** | Noun + Validator | EmailValidator, OrderValidator |

---

## State-of-the-Art Benchmarks (2024)

### HECS vs. Baselines

```
Metric      | JDeodorant | HECS  | Improvement
------------|------------|-------|------------
Precision   | ~61%       | ~85%  | +38.5%
Recall      | ~68%       | ~75%  | +9.7%
F1-Score    | ~64%       | ~92%  | +44.4%
```

### Cross-Language Detection

```
Precision: 66% (moderate)
Recall:    84% (excellent)
```

### Tool Comparison Timeline

```
2012: JDeodorant (structural clustering)
2014: Bavota et al. (structural + semantic LSI)
2018: SSECS (semantic + structural)
2023: LLMRefactor (LLM-based)
2024: HECS (hypergraph neural network) ← Current SOTA
```

---

## Essential Academic Papers - Quick List

1. **Bavota et al. (2014)** - Structural + Semantic combination
   - Precision ~70%, Recall ~65%
   - MaxFlow-MinCut algorithm
   - LSI for semantic analysis

2. **Fokaefs et al. (2012)** - JDeodorant
   - Hierarchical clustering
   - Entity Placement metric
   - Ground truth from expert designers

3. **HECS (2024)** - Current state-of-the-art
   - Hypergraph neural networks
   - 38.5% precision improvement
   - Intra-class dependency analysis

4. **Al-Shaaby et al. (2022)** - Cohesion + Coupling balance
   - Greedy approach
   - Addresses coupling neglect problem
   - Entity Placement ratio

5. **Research Square (2025)** - Metric thresholds
   - Metaheuristic threshold derivation
   - Project-specific ranges
   - Empirical validation

---

## Tool Configuration - Quick Templates

### PMD Configuration

```xml
<rule ref="category/java/design.xml/GodClass">
    <properties>
        <property name="wmc" value="47" />
        <property name="atfd" value="5" />
        <property name="tcc" value="0.33" />
    </properties>
</rule>
```

### SonarQube Thresholds

```
# God Class detection
sonar.java.god_class.loc_threshold=400
sonar.java.god_class.wmc_threshold=47
sonar.java.god_class.lcom_threshold=0.6
```

### Custom Analysis Script

```python
def is_god_class(metrics):
    return (
        metrics['loc'] > 400 and
        metrics['wmc'] > 47 and
        metrics['lcom5'] > 0.6 and
        metrics['tcc'] < 0.33
    )
```

---

## Evaluation Script - Quick Template

```python
# Minimal evaluation
def evaluate(proposals, ground_truth):
    tp = len(proposals & ground_truth)
    fp = len(proposals - ground_truth)
    fn = len(ground_truth - proposals)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0

    return {'precision': precision, 'recall': recall, 'f1': f1}
```

---

## Resources - Quick Links

### Academic
- JDeodorant: https://github.com/tsantalis/JDeodorant
- Refactoring Catalog: https://refactoring.com/catalog/
- Qualitas Corpus: http://qualitascorpus.com/

### Industry
- Refactoring Guru: https://refactoring.guru/
- Martin Fowler: https://martinfowler.com/
- PMD: https://pmd.github.io/

### Tools
- JDeodorant (Eclipse plugin)
- IntelliJ IDEA (built-in refactoring)
- SonarQube (code quality)
- PMD (static analysis)

---

**END OF QUICK REFERENCE**

For detailed information, see:
- `god_class_antipattern_research.md` - Full research documentation
- `extract_class_test_cases_guide.md` - Test case implementation guide
