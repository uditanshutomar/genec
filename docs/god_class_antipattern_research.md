# God Class Anti-Patterns and Extract Class Refactoring: Research Documentation

**Author:** Research compiled from academic sources and industry best practices
**Date:** 2025-12-05
**Purpose:** Comprehensive guide for evaluating Extract Class refactoring tools

---

## Table of Contents

1. [Real-World God Class Characteristics](#1-real-world-god-class-characteristics)
2. [Extract Class Refactoring Best Practices](#2-extract-class-refactoring-best-practices)
3. [Realistic Test Scenarios](#3-realistic-test-scenarios)
4. [Evaluation Criteria](#4-evaluation-criteria)
5. [References](#5-references)

---

## 1. Real-World God Class Characteristics

### 1.1 Definition

A **God Class** (also known as God Object) is one of the most dangerous anti-patterns in software development. It occurs when a single class takes on too many responsibilities, violating the principles of encapsulation, modularity, and the Single Responsibility Principle (SRP).

**Core Characteristics:**
- Hoards too much logic: business rules, data manipulation, UI behavior, and even database access
- Knows too much or does too much
- Creates a tightly coupled mess
- Torpedoes testability and maintainability
- Exhibits an irregular distribution of functionalities in large-sized classes

### 1.2 Detection Metrics and Thresholds

God Classes are identified using a combination of size, complexity, cohesion, and coupling metrics:

#### Primary Metrics (Empirically Validated)

| Metric | Description | Empirical Thresholds | Source |
|--------|-------------|---------------------|---------|
| **LOC** | Lines of Code | 104-407 (project-specific) | Research Square 2025 |
| **WMC** | Weighted Methods per Class (sum of cyclomatic complexity) | 18-72 (project-specific)<br>≥47 (PMD tool) | Research Square 2025 |
| **LCOM** | Lack of Cohesion of Methods | High values indicate low cohesion | Multiple studies |
| **CBO** | Coupling Between Objects | 8-69 (project-specific) | Research Square 2025 |
| **RFC** | Response For a Class | 38-95 (project-specific) | Research Square 2025 |
| **ATFD** | Access To Foreign Data | >5 (PMD tool) | Stack Overflow PMD |
| **TCC** | Tight Class Cohesion | <1/3 (PMD tool) | Stack Overflow PMD |

#### PMD God Class Detection Rule

A class triggers a God Class violation if:
```
WMC >= 47 AND ATFD > 5 AND TCC < 1/3
```

#### Key Findings from Empirical Studies

1. **Threshold values are not universal** - they vary for each project (Research Square, 2025)
2. **Most relevant features** for ML-based detection: LOC type and WMC type
3. **Detection strategy**: High values for WMC and ATFD, low values for TCC
4. **Metric thresholds are significantly effective** in bad smell detection

### 1.3 Common Patterns in God Classes

#### Anti-Pattern Indicators:

1. **Responsibility Overload**
   - Single class handling multiple distinct concerns
   - Mix of business logic, data access, UI logic, and validation
   - Violation of SRP

2. **High Complexity**
   - Dozens or hundreds of methods
   - High cyclomatic complexity per method
   - Deep nesting and long method bodies

3. **Low Cohesion**
   - Methods accessing different subsets of fields
   - Lack of conceptual relationship between methods
   - Multiple "islands" of functionality within one class

4. **High Coupling**
   - Dependencies on many other classes
   - Many classes depending on this class
   - Difficult to test in isolation

### 1.4 Real-World Examples

#### Apache Commons StringUtils

**Characteristics:**
- Described as "probably the most used class from Apache Commons"
- Over 50 static methods for string manipulation
- Covers operations beyond java.lang.String

**Analysis:**
- While large (50+ methods), it's **NOT** considered a true God Class
- Reason: Domain-focused (string operations), business-agnostic, consistent pattern
- Represents a **legitimate utility class** vs. problematic God Class
- All methods share a single responsibility: string manipulation

**Key Distinction:** Utility classes can be large if they maintain:
1. Single domain focus
2. Business-agnostic operations
3. Consistent abstraction level
4. Wide reusability across projects

#### Other Notable Examples

From research literature:
- **Apache Tomcat**: `StandardContext` class (cited for many responsibilities)
- **Spring Framework**: Older `ApplicationContext` implementations
- **JDeodorant Evaluation Dataset**: Used real-world God Classes from 6 different projects

### 1.5 Size Metrics - What's "Too Large"?

#### Empirical Ranges:

- **Small Classes**: < 100 LOC
- **Medium Classes**: 100-300 LOC
- **Large Classes**: 300-500 LOC
- **Very Large (God Class candidates)**: 500-1000+ LOC

**Important Note:** Size alone doesn't make a God Class. A 500-line class with high cohesion and single responsibility may be acceptable, while a 200-line class with multiple unrelated concerns is problematic.

#### Real-World Distribution:

From Qualitas Corpus studies (large collection of open-source Java software):
- Most well-designed classes: 50-200 LOC
- God Class candidates typically: 400+ LOC with low cohesion
- Threshold varies significantly by domain and architecture

---

## 2. Extract Class Refactoring Best Practices

### 2.1 Martin Fowler's Extract Class Criteria

From "Refactoring: Improving the Design of Existing Code":

**When to Apply Extract Class:**

1. **Data Subsets**: Logical units of data grouped together
2. **Operation Subsets**: Operations performed on a subset of data
3. **Separate Changes**: Parts of the class change separately or at different rates
4. **Different Dependencies**: Different parts depend on different external classes
5. **Temporal Coupling**: Methods used together in time but not logically cohesive

**Signs You Need Extract Class:**

- Class has too many instance variables
- Class has groups of methods that always use the same data
- Method names suggest separate responsibilities
- Difficult to name the class without using "and" or "or"
- Class changes for multiple different reasons

### 2.2 Cohesion and Coupling Balance

#### Critical Challenge (MDPI 2022)

> "Most approaches focus on improving the cohesion of the extracted classes yet **neglect the coupling between them**, which can lead to the extraction of **highly coupled classes**."

**The Cohesion-Coupling Trade-off:**
- Increasing cohesion often comes at the price of coupling
- Extract Class must optimize BOTH metrics simultaneously
- Goal: High cohesion within classes, low coupling between classes

#### Recommended Approach

**Entity Placement Metric** (Bavota et al.):
```
EP = Overall System Cohesion / Overall System Coupling
```

This ratio-based metric ensures that both cohesion improvements and coupling increases are considered.

**Best Practice:** A good extraction should:
1. Increase cohesion of both original and extracted class
2. Minimize coupling between them
3. Improve overall system EP score

### 2.3 Structural vs. Semantic Cohesion

#### Two Complementary Approaches

**Structural Cohesion** (Traditional):
- Based on field accesses and method calls
- Measures concrete dependencies
- Examples: LCOM, TCC metrics

**Semantic Cohesion** (Modern):
- Based on naming and conceptual relationships
- Uses Latent Semantic Indexing (LSI)
- Analyzes identifiers, comments, and domain concepts

#### Hybrid Approach (Bavota et al., 2014)

The most effective Extract Class methods combine both:

1. **Structural Analysis**:
   - Methods accessing common fields
   - Method call relationships
   - Parameter passing patterns

2. **Semantic Analysis**:
   - Identifier similarity (method/variable names)
   - Comment analysis
   - Domain concept extraction

3. **Integration**:
   - Weighted graph representation
   - MaxFlow-MinCut algorithm for partitioning
   - Edge weights combine structural + semantic measures

**Key Finding:**
> "The orthogonality between structural and semantic cohesion metrics motivates this work... empirical evaluation highlighted the benefits provided by the combination."

### 2.4 Common Extraction Patterns

#### Pattern 1: Data Clumps Extraction

**Problem:** Same group of 3-4 data items appear together in multiple places

**Example:**
```java
// God Class
class Order {
    private String customerName;
    private String customerEmail;
    private String customerPhone;
    private String shippingAddress;
    private String shippingCity;
    private String shippingZip;
    // ... order processing logic
}

// Refactored
class Customer {
    private String name;
    private String email;
    private String phone;
}

class ShippingAddress {
    private String street;
    private String city;
    private String zip;
}

class Order {
    private Customer customer;
    private ShippingAddress shippingAddress;
    // ... order processing logic
}
```

**Refactoring Steps:**
1. Use Extract Class on instance variables
2. Turn clumps into objects
3. Use Introduce Parameter Object or Preserve Whole Object for methods

#### Pattern 2: Feature Envy Extraction

**Problem:** Method accesses data of another object more than its own

**Detection (Modern GNN Approach):**
- Transform into binary classification on method call graph
- SMOTE Call Graph (SCG) for imbalanced data
- Symmetric Feature Fusion Learning (SFFL)

**Solution:**
- Move method to the class it's envious of, OR
- Extract new class containing the envied data and method

**Impact:** Reduces coupling, improves cohesion, enhances maintainability

#### Pattern 3: Service Extraction

**Problem:** Business logic mixed with data access or UI concerns

**Example:**
```java
// God Class
class ShoppingCart {
    private List<Item> items;

    public void addItem(Item item) { ... }
    public void removeItem(Item item) { ... }
    public double calculateTotal() { ... }
    public double applyDiscount(String code) { ... }
    public double calculateShipping() { ... }
    public void processPayment() { ... }
}

// Refactored
class CartItemCollection {
    private List<Item> items;
    public void addItem(Item item) { ... }
    public void removeItem(Item item) { ... }
}

class PriceCalculator {
    public double calculateTotal(List<Item> items) { ... }
}

class DiscountCalculator {
    public double applyDiscount(double amount, String code) { ... }
}

class ShippingCalculator {
    public double calculateShipping(List<Item> items) { ... }
}

class ShoppingCart {
    private CartItemCollection items;
    private PriceCalculator priceCalc;
    private DiscountCalculator discountCalc;
    private ShippingCalculator shippingCalc;
    // Delegates to appropriate services
}
```

#### Pattern 4: Strategy Pattern Extraction

**Problem:** Multiple algorithms or conditional logic for similar operations

**Solution:**
- Extract each algorithm/variant into separate strategy class
- Use composition instead of inheritance
- Apply Dependency Injection for flexibility

#### Pattern 5: Temporal Coupling Resolution

**Problem:** Files/methods change together over time but aren't logically related

**Detection:** CodeScene temporal coupling analysis

**Solution:**
- Analyze version control history
- Identify co-changing components
- Extract frequently co-changed methods into cohesive unit

### 2.5 Ideal Cohesive Units to Extract

#### Identification Criteria

**Strong Candidates for Extraction:**

1. **Conceptual Groups**
   - Methods that share a common abstraction
   - Related domain concepts
   - Semantic similarity in naming

2. **Structural Groups**
   - Methods accessing the same subset of fields
   - Methods calling each other frequently
   - Methods with shared parameters

3. **Responsibility Groups**
   - Methods that change for the same reason
   - Methods with one well-defined purpose
   - Methods that represent a distinct feature

#### JDeodorant Approach

**Algorithm:** Hierarchical Agglomerative Clustering
- Based on Jaccard distance between class members
- Suggests extractions ranked by Entity Placement metric
- Considers both structural relationships and member usage patterns

**Validation:** Designers manually identify extractable concepts as ground truth

#### Modern ML Approaches

**HECS (2024)** - Hypergraph Learning-Based System:
- Uses intra-class dependency hypergraph
- Neural network for pattern detection
- **Results**: 38.5% increase in precision, 9.7% in recall, 44.4% in F1 vs. JDeodorant

**SFFL + SCG** - For Feature Envy:
- Graph Neural Network approach
- Binary classification on method call graph
- Addresses class imbalance with SMOTE

---

## 3. Realistic Test Scenarios

### 3.1 What Makes a Realistic God Class Test Case?

A good test God Class should contain:

1. **Mixed Cohesion Levels**
   - 2-4 highly cohesive method groups (good extraction candidates)
   - 1-2 loosely related utility methods
   - Some methods with ambiguous placement

2. **Varied Extraction Challenges**
   - Data clumps (easy to detect)
   - Feature envy (moderate difficulty)
   - Temporal coupling (requires history analysis)
   - Subtle semantic relationships (requires domain understanding)

3. **Realistic Complexity**
   - 300-800 LOC (typical problematic range)
   - 15-40 methods
   - 10-20 fields
   - WMC: 30-80
   - LCOM: 0.6-0.9 (high lack of cohesion)

4. **Real-World Patterns**
   - Mix of public and private methods
   - Some method interdependencies
   - Both simple and complex methods
   - Realistic naming conventions

### 3.2 Example Test Scenario: E-Commerce Order Manager

```java
/**
 * God Class Example: OrderManager
 * LOC: ~450
 * Methods: 28
 * Fields: 15
 * WMC: ~55
 * Responsibilities: 5 distinct concerns
 */
public class OrderManager {
    // Customer data (Data Clump #1)
    private String customerName;
    private String customerEmail;
    private String customerPhone;
    private String customerAddress;

    // Order data (Data Clump #2)
    private List<OrderItem> items;
    private String orderId;
    private Date orderDate;
    private OrderStatus status;

    // Payment data (Data Clump #3)
    private String paymentMethod;
    private String cardNumber;
    private double totalAmount;

    // Shipping data (Data Clump #4)
    private String shippingMethod;
    private String trackingNumber;
    private Date estimatedDelivery;

    // Notification config (Data Clump #5)
    private boolean emailNotifications;

    // COHESIVE GROUP 1: Customer Management (Should extract to Customer class)
    public void setCustomerInfo(String name, String email, String phone) { ... }
    public String getCustomerName() { ... }
    public String getCustomerEmail() { ... }
    public boolean validateCustomerEmail() { ... }
    public String getCustomerDisplayName() { ... }

    // COHESIVE GROUP 2: Order Item Management (Should extract to Cart/OrderItems class)
    public void addItem(OrderItem item) { ... }
    public void removeItem(String itemId) { ... }
    public void updateItemQuantity(String itemId, int quantity) { ... }
    public int getTotalItemCount() { ... }
    public List<OrderItem> getItems() { ... }

    // COHESIVE GROUP 3: Pricing & Discounts (Should extract to PriceCalculator)
    public double calculateSubtotal() { ... }
    public double calculateTax() { ... }
    public double applyDiscountCode(String code) { ... }
    public double calculateShippingCost() { ... }
    public double calculateTotal() { ... }

    // COHESIVE GROUP 4: Payment Processing (Should extract to PaymentProcessor)
    public boolean validatePaymentMethod() { ... }
    public boolean processPayment() { ... }
    public void refundPayment() { ... }
    public String maskCardNumber() { ... }

    // COHESIVE GROUP 5: Shipping & Tracking (Should extract to ShippingManager)
    public void setShippingMethod(String method) { ... }
    public void generateTrackingNumber() { ... }
    public Date calculateEstimatedDelivery() { ... }
    public String getShippingStatus() { ... }

    // COHESIVE GROUP 6: Notifications (Should extract to NotificationService)
    public void sendOrderConfirmationEmail() { ... }
    public void sendShippingNotification() { ... }
    public void sendDeliveryNotification() { ... }

    // UTILITY METHODS (Ambiguous placement - could stay or extract)
    public String generateOrderId() { ... }
    public void logOrderEvent(String event) { ... }
    public String formatDate(Date date) { ... }
}
```

**Expected Extractions:**

1. **Customer** (4 fields, 5 methods) - High cohesion, clear responsibility
2. **OrderItems** (1 field, 5 methods) - High cohesion, collection management
3. **PriceCalculator** (0-1 fields, 5 methods) - Stateless service
4. **PaymentProcessor** (3 fields, 4 methods) - Sensitive data isolation
5. **ShippingManager** (3 fields, 4 methods) - Logistics concern
6. **NotificationService** (1 field, 3 methods) - Communication concern

**Remaining OrderManager:**
- Core orchestration logic
- Coordination between extracted classes
- Order state management
- ~100-150 LOC, much more maintainable

### 3.3 Edge Cases and Challenges

#### Challenge 1: Shared Dependencies

**Scenario:** Multiple method groups need the same field

**Example:**
```java
private Date orderDate; // Used by pricing, shipping, and notifications
```

**Tool Challenge:** Deciding which extracted class should own it
**Good Solution:** Pass as parameter or use shared value object
**Bad Solution:** Duplicate the field in multiple classes

#### Challenge 2: Method Interdependencies

**Scenario:** Method A calls Method B, but they belong to different cohesive groups

**Example:**
```java
// In pricing group
public double calculateTotal() {
    double subtotal = calculateSubtotal();
    double shipping = calculateShippingCost(); // calls shipping group method
    return subtotal + shipping;
}
```

**Tool Challenge:** Breaking call dependencies
**Good Solution:** Use dependency injection, interfaces, or callbacks
**Bad Solution:** Create circular dependencies between extracted classes

#### Challenge 3: Temporal vs. Logical Cohesion

**Scenario:** Methods called in sequence but not logically related

**Example:**
```java
public void processOrder() {
    validateCustomer();      // Customer concern
    checkInventory();        // Inventory concern
    processPayment();        // Payment concern
    arrangeShipping();       // Shipping concern
}
```

**Tool Challenge:** Recognizing orchestration vs. cohesive responsibility
**Good Solution:** Keep orchestration in original class, extract details
**Bad Solution:** Extract the entire workflow into one bloated class

#### Challenge 4: Polymorphic Behavior

**Scenario:** Different implementations based on type/state

**Example:**
```java
public double calculateShipping() {
    if (shippingMethod.equals("express")) {
        return expressShippingCost();
    } else if (shippingMethod.equals("standard")) {
        return standardShippingCost();
    }
    // ... more conditions
}
```

**Tool Challenge:** Recognizing strategy pattern opportunity
**Good Solution:** Extract to ShippingStrategy interface with implementations
**Bad Solution:** Extract as-is, missing design improvement opportunity

### 3.4 Benchmark Datasets

#### Available Datasets

1. **JDeodorant Evaluation Set**
   - 3 systems with manually identified extractions
   - Designer-validated ground truth
   - Mix of synthetic and real-world

2. **Qualitas Corpus**
   - Large collection of open-source Java projects
   - Widely used in empirical studies
   - Contains known God Classes from 24 software systems

3. **HECS Benchmark (2024)**
   - Large-scale real-world dataset
   - Used for state-of-the-art evaluation
   - Compared against JDeodorant, SSECS, LLMRefactor

#### Creating Your Own Test Cases

**Minimal Realistic Test:**
- 1 God Class with 3-5 clear extraction opportunities
- 200-400 LOC
- At least one data clump
- At least one service extraction candidate
- Mix of easy and moderate difficulty extractions

**Comprehensive Test Suite:**
- 5-10 God Classes of varying sizes (200-800 LOC)
- Different domain contexts (e-commerce, finance, healthcare, etc.)
- Various complexity levels (easy, moderate, hard)
- Edge cases: shared dependencies, circular calls, polymorphism
- Both utility classes and domain classes

---

## 4. Evaluation Criteria

### 4.1 Correctness Metrics

#### Ground Truth Establishment

**Manual Expert Validation:**
1. Expert developers identify extractable concepts
2. Document expected extractions with rationale
3. Use as ground truth for precision/recall calculation

**Automated Validation:**
1. Verify extracted code compiles
2. Ensure tests still pass
3. Check no behavior changes (regression testing)

#### Precision and Recall

**Precision** = (Correct Extractions) / (Total Proposed Extractions)
- Measures: How many suggested extractions are actually good?
- High precision = Few false positives
- Target: >70% (excellent: >85%)

**Recall** = (Correct Extractions) / (Total Possible Extractions)
- Measures: How many good extractions were found?
- High recall = Few false negatives
- Target: >60% (excellent: >80%)

**F1-Score** = 2 × (Precision × Recall) / (Precision + Recall)
- Harmonic mean of precision and recall
- Balanced measure of overall performance
- Target: >65% (excellent: >80%)

#### State-of-the-Art Benchmarks (2024)

**HECS Performance vs. Baselines:**
- Precision: +38.5% improvement over JDeodorant
- Recall: +9.7% improvement
- F1-Score: +44.4% improvement

**Cross-Language Detection:**
- Recall: 84% (excellent)
- Precision: 66% (moderate, higher false positives)

### 4.2 Quality Indicators

#### Cohesion Improvement

**LCOM5 (Lack of Cohesion 5):**
```
LCOM5 = (m - sum(mA)/a) / (m - 1)
```
Where:
- m = number of methods
- a = number of fields
- mA = methods accessing each field

**Range:** [0, 1]
- 0 = perfect cohesion
- 1 = no cohesion

**Target:** Both original and extracted classes should have LCOM5 < 0.5 (ideally < 0.3)

**TCC (Tight Class Cohesion):**
```
TCC = NDC / NP
```
Where:
- NDC = directly connected method pairs
- NP = maximum possible connections

**Range:** [0, 1]
**Target:** Both classes should have TCC > 0.5 (ideally > 0.7)

#### Coupling Reduction

**CBO (Coupling Between Objects):**
- Count of classes this class depends on
- **Target:** Original class CBO should decrease
- **Warning:** Extracted classes should have low coupling to each other

**Afferent/Efferent Coupling:**
- Ca (Afferent): Classes depending on this class
- Ce (Efferent): Classes this class depends on

**Instability Metric:**
```
I = Ce / (Ca + Ce)
```
**Range:** [0, 1]
- 0 = maximally stable (only incoming dependencies)
- 1 = maximally unstable (only outgoing dependencies)

**Target:** Reasonable balance, avoid I > 0.8

#### Naming Quality

**Good Class Names:**
1. **Clear and Specific**
   - "Customer" not "Data"
   - "PriceCalculator" not "Calculator"
   - "ShippingManager" not "Manager"

2. **Domain-Relevant**
   - Reflects business/domain concepts
   - Meaningful to developers and stakeholders
   - Self-documenting

3. **Consistent Level of Abstraction**
   - Not mixing high-level and low-level concepts
   - Appropriate granularity

**Red Flags:**
- Generic names: "Util", "Helper", "Manager" (without context)
- Numbers: "ExtractedClass1", "OrderManager2"
- Vague terms: "Data", "Info", "Stuff"

**Evaluation:**
- Manual review by domain experts
- Semantic similarity analysis with existing domain vocabulary
- Name length and clarity (typically 1-3 words)

### 4.3 Practical Quality Measures

#### Code Size Distribution

**Before Extraction:**
- God Class: 500+ LOC

**After Extraction (Target):**
- Original Class: 100-200 LOC (orchestration)
- Extracted Classes: 50-150 LOC each
- Total LOC may increase slightly (acceptable for better organization)

#### Method Distribution

**Before:**
- 30-50 methods in one class

**After:**
- Original: 5-15 methods
- Each extracted: 3-10 methods

#### Maintainability Metrics

**Cyclomatic Complexity:**
- Per method: < 10 (excellent: < 5)
- Per class: < 50 (excellent: < 30)

**Depth of Inheritance:**
- Extracted classes should be shallow (DIT ≤ 3)

**Response for Class (RFC):**
- Should decrease for original class
- Should be reasonable for extracted classes (< 30)

### 4.4 Signs of Good vs. Bad Extractions

#### Good Extraction Indicators

✅ **High Cohesion**
- Methods in extracted class clearly related
- Single, well-defined responsibility
- LCOM5 < 0.3, TCC > 0.7

✅ **Low Coupling**
- Few dependencies between original and extracted
- No circular dependencies
- Clear, minimal interface

✅ **Meaningful Names**
- Class name reflects domain concept
- Methods make sense in new context
- No "ExtractedClass1" names

✅ **Independent Testing**
- Extracted class can be tested in isolation
- Clearer test scenarios
- Easier mocking

✅ **Clear Responsibility**
- Can describe class purpose in one sentence
- Single reason to change
- No "and" or "or" in description

✅ **Improved Readability**
- Easier to understand both classes
- Clearer code organization
- Better navigation

#### Bad Extraction Indicators

❌ **High Coupling**
- Extracted class tightly coupled to original
- Many parameters passed back and forth
- Circular dependencies

❌ **Low Cohesion**
- Methods in extracted class unrelated
- Multiple responsibilities
- LCOM5 > 0.7

❌ **Poor Names**
- Generic or numbered names
- Doesn't reflect domain concept
- Confusing or misleading

❌ **Over-Fragmentation**
- Too many tiny classes (< 30 LOC each)
- Excessive indirection
- Harder to understand than original

❌ **Artificial Grouping**
- Methods grouped by implementation detail, not concept
- No semantic relationship
- Just moving code around

❌ **Broken Encapsulation**
- Excessive getters/setters added
- Internal state exposed
- Violated information hiding

### 4.5 Automated Evaluation Pipeline

#### Step 1: Static Analysis
```python
def evaluate_extraction(original_class, extracted_classes):
    metrics = {}

    # Cohesion metrics
    for cls in [original_class] + extracted_classes:
        metrics[cls.name] = {
            'lcom5': calculate_lcom5(cls),
            'tcc': calculate_tcc(cls),
            'loc': count_loc(cls),
            'methods': count_methods(cls),
            'fields': count_fields(cls)
        }

    # Coupling metrics
    metrics['coupling'] = {
        'original_cbo': calculate_cbo(original_class),
        'inter_extraction_coupling': calculate_coupling_between(extracted_classes),
        'extraction_to_original_coupling': calculate_coupling_to_original(extracted_classes, original_class)
    }

    return metrics
```

#### Step 2: Compilation & Testing
```python
def validate_extraction(refactored_code):
    results = {}

    # Compilation
    results['compiles'] = compile_code(refactored_code)

    # Tests pass
    results['tests_pass'] = run_tests(refactored_code)

    # No behavior change
    results['behavior_preserved'] = run_regression_tests(refactored_code)

    return all(results.values())
```

#### Step 3: Manual Review
```python
def manual_review_checklist():
    return {
        'naming_quality': "Are class and method names clear and domain-relevant?",
        'responsibility_clarity': "Can each class be described in one sentence?",
        'coupling_reasonableness': "Are dependencies minimal and justified?",
        'cohesion_subjective': "Do methods in each class 'belong together'?",
        'overall_improvement': "Is the refactored code easier to understand?"
    }
```

#### Step 4: Precision/Recall Calculation
```python
def calculate_precision_recall(proposed_extractions, ground_truth_extractions):
    true_positives = len(proposed_extractions & ground_truth_extractions)
    false_positives = len(proposed_extractions - ground_truth_extractions)
    false_negatives = len(ground_truth_extractions - proposed_extractions)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'true_positives': true_positives,
        'false_positives': false_positives,
        'false_negatives': false_negatives
    }
```

### 4.6 Comparative Benchmarks

| Tool/Approach | Precision | Recall | F1-Score | Year | Notes |
|---------------|-----------|--------|----------|------|-------|
| JDeodorant | Baseline | Baseline | Baseline | 2012 | Structural + hierarchical clustering |
| Bavota et al. | ~70% | ~65% | ~67% | 2014 | Structural + semantic (LSI) |
| SSECS | Moderate | Moderate | Moderate | ~2018 | Structural and semantic |
| LLMRefactor | Variable | Variable | Variable | 2023 | LLM-based approach |
| HECS | 85%+ | 75%+ | 80%+ | 2024 | Hypergraph neural network (SOTA) |

**Note:** Exact numbers vary by dataset and evaluation methodology.

---

## 5. References

### Academic Papers

1. **Bavota, G., et al. (2014).** "Automating extract class refactoring: an improved method and its evaluation." *Empirical Software Engineering*, 19(6), 1617-1664.
   - [ACM Digital Library](https://dl.acm.org/doi/10.1007/s10664-013-9256-x)

2. **Fokaefs, M., et al. (2012).** "Identification and application of Extract Class refactorings in object-oriented systems." *Journal of Systems and Software*, 85(10), 2241-2260.
   - [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0164121212001057)

3. **Bavota, G., et al. (2011).** "Identifying Extract Class refactoring opportunities using structural and semantic cohesion measures." *Journal of Systems and Software*, 84(3), 397-414.
   - [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0164121210003195)

4. **HECS (2024).** "A Hypergraph Learning-Based System for Detecting Extract Class Refactoring Opportunities." *Proceedings of the 33rd ACM SIGSOFT International Symposium on Software Testing and Analysis*.
   - [ACM Digital Library](https://dl.acm.org/doi/10.1145/3650212.3685307)

5. **Al-Shaaby, A., et al. (2022).** "Extract Class Refactoring Based on Cohesion and Coupling: A Greedy Approach." *Computers*, 11(8), 123.
   - [MDPI](https://www.mdpi.com/2073-431X/11/8/123)

6. **Research Square (2025).** "Thresholds Derivation of Software Code Metrics for God Class Detection Using Metaheuristic Approaches."
   - [Research Square](https://www.researchsquare.com/article/rs-6255844/v1)

7. **Feature Envy Detection (2024).** "Efficient feature envy detection and refactoring based on graph neural network." *Automated Software Engineering*.
   - [ACM Digital Library](https://dl.acm.org/doi/abs/10.1007/s10515-024-00476-3)

### Online Resources

8. **Refactoring Guru.** "God Object / God Class."
   - [refactoring.guru](https://refactoring.guru/refactoring/smells/couplers)

9. **Martin Fowler.** "Refactoring: Improving the Design of Existing Code."
   - [martinfowler.com](https://martinfowler.com/books/refactoring.html)

10. **Metridev.** "God Class: The Definitive Guide to Identifying and Avoiding It."
    - [metridev.com](https://www.metridev.com/metrics/god-class-the-definitive-guide-to-identifying-and-avoiding-it/)

11. **ByteCrafted.** "Refactoring Code for Better Coupling and Cohesion."
    - [bytecrafted.dev](https://bytecrafted.dev/refactoring-coupling-cohesion/)

12. **Microsoft Learn.** "Patterns in Practice: Cohesion And Coupling."
    - [Microsoft Learn](https://learn.microsoft.com/en-us/archive/msdn-magazine/2008/october/patterns-in-practice-cohesion-and-coupling)

13. **Apache Commons Lang StringUtils.**
    - [Apache Commons](https://commons.apache.org/proper/commons-lang/apidocs/org/apache/commons/lang3/StringUtils.html)

14. **JDeodorant GitHub Repository.**
    - [GitHub](https://github.com/tsantalis/JDeodorant)

15. **CodeScene Documentation.** "Temporal Coupling."
    - [CodeScene Docs](https://docs.enterprise.codescene.io/versions/2.4.2/guides/technical/temporal-coupling.html)

### Industry Best Practices

16. **thoughtbot.** "Refactoring, Extraction, and Naming."
    - [Upcase Tutorial](https://thoughtbot.com/upcase/videos/refactoring-extraction-naming)

17. **CodeSignal Learn.** "Large Class: Extract Class Refactoring."
    - [CodeSignal](https://codesignal.com/learn/courses/refactoring-by-leveraging-your-tests-with-java-junit/lessons/refactoring-large-classes-using-the-extract-class-pattern)

18. **Baeldung.** "String Processing with Apache Commons Lang 3."
    - [Baeldung](https://www.baeldung.com/string-processing-commons-lang)

19. **Stack Overflow.** "PMD rule God Class - understanding the metrics."
    - [Stack Overflow](https://stackoverflow.com/questions/37389376/pmd-rule-god-class-understanding-the-metrics)

20. **Rightmove Tech Blog.** "Why Util Classes Suck."
    - [Rightmove Blog](https://rightmove.blog/why-util-classes-suck/)

---

## Appendix A: Quick Reference - God Class Metrics

| Metric | Formula | Threshold | Interpretation |
|--------|---------|-----------|----------------|
| LOC | Lines of Code | >400 | Class size |
| WMC | Σ Cyclomatic Complexity | >47 | Total complexity |
| LCOM5 | (m - Σ(mA)/a) / (m-1) | >0.6 | Low cohesion |
| TCC | NDC / NP | <0.33 | Low cohesion |
| CBO | Count of coupled classes | >15 | High coupling |
| RFC | Methods + called methods | >50 | Large interface |
| ATFD | Access to foreign data | >5 | Feature envy |

## Appendix B: Extract Class Checklist

**Before Extraction:**
- [ ] Identify 2-4 cohesive method groups
- [ ] Calculate baseline metrics (LCOM5, TCC, CBO)
- [ ] Document expected responsibilities
- [ ] Review with domain expert

**During Extraction:**
- [ ] Choose meaningful class names
- [ ] Minimize coupling between classes
- [ ] Ensure each class has single responsibility
- [ ] Maintain encapsulation
- [ ] Update tests accordingly

**After Extraction:**
- [ ] Verify code compiles
- [ ] Run all tests (must pass)
- [ ] Calculate new metrics (should improve)
- [ ] Review code readability
- [ ] Document refactoring rationale

## Appendix C: Common Pitfalls

1. **Over-extraction**: Creating too many tiny classes
2. **Under-extraction**: Not extracting enough, leaving bloated class
3. **Wrong grouping**: Grouping by implementation vs. concept
4. **High coupling**: Extracted classes too dependent on each other
5. **Poor naming**: Generic names that don't convey meaning
6. **Broken encapsulation**: Exposing too much internal state
7. **Circular dependencies**: Extracted classes calling back to original
8. **Ignoring semantics**: Only using structural metrics, missing domain concepts

---

**End of Document**
