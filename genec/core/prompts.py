"""
LLM Prompts for GenEC (Generative Evolutionary Coupling).
Contains the prompt templates, personas, and few-shot examples used by the LLM interface.
"""

# ==============================================================================
# 1. PERSONA & SYSTEM PROMPT
# ==============================================================================
SYSTEM_PROMPT = """You are a Senior Java Architect specializing in modernizing legacy codebases.
Your goal is to identify cohesive responsibilities within a "God Class" and extract them into clean, maintainable components following SOLID principles.

**Refactoring Type:** Extract Class
**Goal:** Create a new class with high cohesion and low coupling that encapsulates a single, well-defined responsibility.
"""

# ==============================================================================
# 2. FEW-SHOT EXAMPLES
# ==============================================================================

# Example 1: Service Extraction (Logic-heavy)
EXAMPLE_SERVICE_EXTRACTION = """
<example>
<cluster_members>
Methods:
  - public boolean validateEmail(String email)
    Description: Checks if email format is valid using regex pattern.
  - public boolean validatePhone(String phone)
    Description: Validates phone number format.
  - public boolean validateAddress(String address)
    Description: Checks if address contains required components.
Fields:
  - EMAIL_PATTERN
  - PHONE_PATTERN
</cluster_members>

<reasoning>
Step 1: Primary Responsibility Analysis
These methods share a common responsibility: input validation. They validate different types of user input (email, phone, address) using pattern matching.

Step 2: Shared Concept/Domain
All methods belong to the "validation" domain. They share validation patterns and have no business logic beyond checking format correctness.

Step 3: Extraction Benefits
- Improves Single Responsibility Principle: Validation logic is isolated
- Enhances Reusability: Validator can be used by multiple classes
- Reduces Complexity: Original class becomes simpler and more focused

Step 4: Design Justification
Follows the Extract Class refactoring pattern to separate validation concerns. The new class will have high cohesion (all methods validate input) and low coupling (minimal dependencies on other classes).
</reasoning>

<class_name>InputValidator</class_name>

<rationale>
These methods form a cohesive validation unit that should be extracted into an InputValidator class. They share validation patterns, have a single clear responsibility (input validation), and are frequently reused together. Extracting them improves code organization by separating validation concerns from business logic.
</rationale>
</example>
"""

# Example 2: Data/Value Object Extraction (Data-heavy)
EXAMPLE_DATA_EXTRACTION = """
<example>
<cluster_members>
Fields:
  - private String street
  - private String city
  - private String zipCode
  - private String country
Methods:
  - public String getFullAddress()
    Description: Returns formatted address string.
  - public boolean isValidZip()
    Description: Validates zip code format.
</cluster_members>

<reasoning>
Step 1: Primary Responsibility Analysis
These fields and methods represent a cohesive set of data: a physical address. The methods operate exclusively on these fields.

Step 2: Shared Concept/Domain
They represent the "Address" domain concept. This is a classic "Data Clump" or "Value Object".

Step 3: Extraction Benefits
- Encapsulation: Address logic is centralized.
- Reusability: Address can be used in other classes (e.g., Shipping, Billing).
- Type Safety: Passing an Address object is safer than passing 4 strings.

Step 4: Design Justification
Extract Class refactoring to create a Value Object.
</reasoning>

<class_name>Address</class_name>

<rationale>
These fields form a logical "Address" entity. Extracting them into a value object improves type safety and encapsulates address-related formatting and validation logic.
</rationale>
</example>
"""

FEW_SHOT_EXAMPLES = f"{EXAMPLE_SERVICE_EXTRACTION}\n{EXAMPLE_DATA_EXTRACTION}"

# ==============================================================================
# 3. MAIN PROMPT TEMPLATE
# ==============================================================================
MAIN_PROMPT_TEMPLATE = """
===== FEW-SHOT EXAMPLES =====
{few_shot_examples}

===== YOUR TASK =====

**Cluster Members (Signatures & Context):**
{context_str}

{evo_context}

**Instructions:**
Before suggesting a class name, please think step-by-step using the following chain-of-thought reasoning:

1. **Primary Responsibility Analysis**: What is the main responsibility shared by these methods? What do they collectively accomplish?

2. **Shared Concept/Domain**: What domain concept or abstraction do these members represent? Are they part of a cohesive subsystem?

3. **Extraction Benefits**: How will extracting these members improve the original class? Consider:
   - Single Responsibility Principle
   - Code reusability
   - Complexity reduction
   - Testability

4. **Design Justification**: Which object-oriented principle or design pattern supports this extraction?

After your step-by-step analysis, provide:
- A descriptive Java class name (UpperCamelCase, noun describing single responsibility)
- A concise rationale (2-3 sentences) explaining why these members belong together

**Naming Constraints (IMPORTANT):**
- AVOID generic suffixes that obscure responsibility:
  - DO NOT use: Service, Manager, Processor, Handler, Helper, Utility, Controller, Orchestrator
  - These are code smells - they indicate vague responsibilities
- PREFER specific role-based names that clearly convey what the class DOES:
  - Calculator, Validator, Formatter, Parser, Builder, Converter
  - Collection, Repository, Cache, Pool, Registry, Factory
  - Reader, Writer, Encoder, Decoder, Mapper, Transformer
- The name should describe the SINGLE RESPONSIBILITY, not a generic category
- Examples of good naming:
  - PriceCalculator (calculates prices) instead of OrderProcessor
  - ShippingCalculator (computes shipping) instead of FulfillmentService  
  - NotificationSender (sends notifications) instead of NotificationManager
  - InventoryTracker (tracks inventory) instead of InventoryHandler

**Quality Guidelines:**
- Class name must be a valid Java identifier (letters, digits, underscores only)
- Class name should clearly convey the single responsibility
- Rationale should reference cohesion, coupling, or design principles

**Output Format:**
Provide your response in the following XML format:

<reasoning>
Step 1: Primary Responsibility Analysis
[Your analysis here]

Step 2: Shared Concept/Domain
[Your analysis here]

Step 3: Extraction Benefits
[Your analysis here]

Step 4: Design Justification
[Your analysis here]
</reasoning>

<class_name>ProposedClassName</class_name>

<rationale>
Your 2-3 sentence explanation here.
</rationale>

<confidence>0.85</confidence>  # Rate your confidence (0.0-1.0) in this suggestion

**Important:** Provide ONLY the XML tags specified above. Do not include code generation.
"""

# ==============================================================================
# 4. CRITIQUE PROMPT
# ==============================================================================
CRITIQUE_PROMPT_TEMPLATE = """Review this Extract Class refactoring suggestion:

**Proposed Class Name:** {class_name}

**Rationale:** {rationale}

**Cluster Members:**
{cluster_members}

**Critique Task:**
Evaluate the suggestion against these strict criteria:

1. **Hallucination Check**: Did the suggestion invent any new methods or fields that don't exist in the input?
2. **Dependency Check**: Does the new class have access to all required dependencies?
3. **Naming**: Is the name specific (e.g., `OrderValidator`) rather than generic (`OrderHelper`)?
4. **SRP**: Does the new class have exactly one reason to change?

**Output:**
If improvements are needed, provide a **refined** suggestion in the standard XML format.
If the original is already optimal, respond with the same suggestion and confidence 0.95+.

<reasoning>
[Critique analysis]
</reasoning>

<class_name>RefinedClassName</class_name>

<rationale>
Improved rationale addressing the critique points.
</rationale>

<confidence>0-1 score</confidence>
"""
