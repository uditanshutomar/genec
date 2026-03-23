# Ground Truth Annotation Rubric for Extract Class Refactoring

## Purpose

This rubric guides manual identification of Extract Class opportunities in God Classes.
Used to create expert ground truth alongside automated RefactoringMiner ground truth.

## Annotator Instructions

For each God Class in the benchmark set:

### Step 1: Read the Class
- Read through the entire class source code
- Note the total number of methods, fields, and LOC
- Identify the main responsibilities the class handles

### Step 2: Identify Responsibilities
List all distinct responsibilities you observe. A "responsibility" is a cohesive set of operations that:
- Share a conceptual purpose (e.g., "serialization", "caching", "validation")
- Operate on related data (shared fields or parameters)
- Could reasonably exist as a standalone class

### Step 3: For Each Responsibility, Identify Members
For each identified responsibility, list:
- **Methods**: Method signatures that belong to this responsibility
- **Fields**: Fields exclusively or primarily used by these methods
- **Rationale**: One sentence explaining why these members belong together

### Step 4: Assess Extractability
For each responsibility group, rate extractability (1-3):
1. **Clearly extractable**: Methods are self-contained, few external dependencies
2. **Extractable with effort**: Some shared state needs delegation pattern
3. **Not extractable**: Too entangled with rest of class (circular dependencies)

Only groups rated 1 or 2 should be included in the ground truth.

### Step 5: Suggest Class Name
Provide a descriptive class name following Java naming conventions.
Prefer specific names (e.g., "ScratchBufferPool") over generic ones ("IOUtilsHelper").

## Agreement Criteria

Two annotators independently annotate each class. Agreement is measured by:
- **Jaccard similarity** of method sets per identified group (threshold: 0.5 for partial match, 0.8 for full match)
- **Cohen's kappa** on the number of extractable groups per class

Disagreements are resolved through discussion. The resolved set becomes ground truth.

## Output Format

```json
{
  "class_name": "IOUtils",
  "project": "commons-io",
  "annotator": "A1",
  "responsibilities": [
    {
      "name": "ScratchBufferPool",
      "methods": ["getScratchBuffer()", "releaseScratchBuffer(byte[])", "getDefaultBufferSize()"],
      "fields": ["SCRATCH_BUFFER_TLS", "DEFAULT_BUFFER_SIZE"],
      "rationale": "Manages thread-local scratch buffers for efficient I/O operations",
      "extractability": 1
    }
  ]
}
```
