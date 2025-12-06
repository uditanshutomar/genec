# JDeodorant Comparison Guide

This guide details how to manually run JDeodorant to generate baseline data for comparison with GenEC (RQ3).

## 1. Prerequisites

- **Eclipse IDE**: "Eclipse IDE for Java Developers" (2020-06 or newer recommended)
- **Java**: JDK 11 or newer
- **JDeodorant Plugin**: Update site: `http://jdeodorant.com/update`

## 2. Installation

1. Open Eclipse
2. Go to `Help` -> `Install New Software...`
3. Click `Add...`
   - Name: `JDeodorant`
   - Location: `http://jdeodorant.com/update`
4. Select `JDeodorant` and install
5. Restart Eclipse

## 3. Experiment Setup

We will compare JDeodorant and GenEC on **10 specific god classes** from the MLCQ dataset.

### 3.1 Selected God Classes

| ID | Class Name | Project | Severity |
|----|------------|---------|----------|
| 1 | `JobSchedulerService` | Apache Usergrid | Major |
| 2 | `LiveSignalEnforcement` | Eclipse Ditto | N/A |
| 3 | `UnorderedPartitionedKVWriter` | Apache Tez | Critical |
| 4 | `DimsDataList` | Eclipse DawnSci | Critical |
| 5 | `StringUtils` | Apache Commons Lang | N/A (Classic) |
| 6 | `DateUtils` | Apache Commons Lang | N/A (Classic) |
| 7 | `ArrayUtils` | Apache Commons Lang | N/A (Classic) |
| 8 | `CatalogBuilder` | Apache Camel | Major |
| 9 | `DefaultCamelContext` | Apache Camel | Critical |
| 10 | `HBMContext` | Hibernate | Critical |

### 3.2 Preparing the Workspace

1. Create a folder `jdeodorant_eval_workspace`
2. For each class above:
   - Clone the repo: `git clone <url>`
   - Checkout the specific commit (from `mlcq_godclasses.csv`)
   - Import into Eclipse as "Existing Maven Project" or "Java Project"

## 4. Running JDeodorant

For each project in Eclipse:

1. Right-click the project in "Package Explorer"
2. Select `JDeodorant` -> `God Class`
3. In the "God Class" view:
   - Select the target class (e.g., `JobSchedulerService`)
   - Click `Identify Bad Smells`
4. Wait for analysis to complete
5. Double-click the result to see "Extract Class" suggestions

## 5. Data Collection

Record the following for each class in `evaluation/baselines/jdeodorant_results.csv`:

| Field | Description |
|-------|-------------|
| `class_name` | Name of the god class |
| `detected` | Did JDeodorant flag it as God Class? (Yes/No) |
| `suggestions_count` | Number of "Extract Class" refactorings suggested |
| `suggested_names` | Names of extracted classes (e.g., `ExtractedClass_1`) |
| `methods_extracted` | List of methods in the extracted class |
| `fields_extracted` | List of fields in the extracted class |

### Example Entry

```csv
class_name,detected,suggestions_count,suggested_names,methods_extracted
JobSchedulerService,Yes,1,"StateManager","checkState,updateState"
```

## 6. Comparison Metrics

Once data is collected, we will compare:

1. **Detection Overlap**: Does JDeodorant find the same god classes as GenEC?
2. **Naming Quality**: JDeodorant usually suggests generic names (e.g., `ExtractedClass`). GenEC uses LLM for semantic names.
3. **Cluster Similarity**: Jaccard index of methods in JDeodorant's cluster vs GenEC's cluster.
   - *Hypothesis*: GenEC clusters will be more cohesive due to evolutionary coupling.

## 7. Troubleshooting

- **"Project not analyzed"**: Make sure the project builds in Eclipse (no red errors). JDeodorant requires a valid AST.
- **"No smells found"**: Try adjusting thresholds in `Window` -> `Preferences` -> `JDeodorant` -> `God Class`.
- **Eclipse hangs**: JDeodorant can be slow on large projects. Increase heap size in `eclipse.ini` (`-Xmx4G`).
