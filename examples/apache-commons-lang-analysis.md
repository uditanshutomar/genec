# GenEC Analysis: Apache Commons Lang StringUtils

**Date**: November 28, 2025
**Target**: `org.apache.commons.lang3.StringUtils`
**Repository**: https://github.com/apache/commons-lang
**File Size**: 9,222 lines of code

## Overview

This document shows the results of running GenEC on the real-world Apache Commons Lang StringUtils class, demonstrating GenEC's ability to analyze large, complex production code.

## Class Characteristics

StringUtils is a well-known utility class from Apache Commons Lang that provides string manipulation methods. It's a classic example of a large utility class that has grown over time.

### Size Metrics
- **Lines of Code**: 9,222
- **Number of Methods**: 243
- **Number of Fields**: 10

### Cohesion Metrics (Before Refactoring)

| Metric | Value | Interpretation |
|--------|-------|----------------|
| LCOM5 | 0.969 | Very high - indicates low cohesion, strong candidate for refactoring |
| TCC (Tight Class Cohesion) | 0.066 | Low - only 6.6% of method pairs are tightly related |
| CBO (Coupling Between Objects) | 9 | Moderate coupling to other classes |

**Analysis**: The high LCOM5 (0.969) and low TCC (0.066) strongly indicate that StringUtils contains multiple unrelated groups of methods that could be extracted into separate classes.

## Dependency Graph Analysis

GenEC built a comprehensive dependency graph capturing method calls and field accesses:

| Graph Metric | Value | Interpretation |
|--------------|-------|----------------|
| Nodes | 252 | 243 methods + 9 fields + constructor |
| Edges | 2,019 | Method-to-method and method-to-field dependencies |
| Density | 0.064 | Relatively sparse - not all methods interact |
| Connected Components | 19 | 19 independent groups of methods |
| Average Clustering Coefficient | 0.567 | Moderate local clustering |
| Average Degree | 16.0 | Each method interacts with ~16 other elements on average |

**Key Finding**: The graph has **19 connected components**, meaning there are 19 completely independent groups of methods that don't interact with each other - strong evidence for extraction opportunities.

## Cluster Detection Results

GenEC applied the Louvain community detection algorithm to identify cohesive method groups:

| Stage | Count | Description |
|-------|-------|-------------|
| **Detected** | 24 clusters | Initial clusters found by Louvain algorithm |
| **Filtered** | 5 clusters | Clusters meeting minimum size and quality thresholds |
| **Ranked** | 5 clusters | Top clusters ranked by extraction benefit |

### Filtering Criteria
- Minimum cluster size: 2 methods
- Maximum cluster size: 40 methods (configurable)
- Quality threshold: Based on modularity and internal cohesion

## Performance

GenEC completed the analysis in approximately **4 seconds** (stages 1-4):

| Stage | Duration | Description |
|-------|----------|-------------|
| Stage 1 | ~0.2s | Static dependency analysis (243 methods) |
| Stage 2 | ~0.05s | Git history mining |
| Stage 3 | ~0.02s | Graph building and fusion (2,019 edges) |
| Stage 4 | ~0.06s | Cluster detection with Louvain |
| **Total** | **~0.3s** | Analysis complete (excluding LLM generation) |

**Note**: LLM generation (Stage 5) was not completed in this run due to missing API key, but would typically add 15-45 seconds (3-5s per cluster × 5 clusters).

## Interpretation

### What GenEC Found

1. **Low Cohesion**: LCOM5 of 0.969 indicates StringUtils is essentially a collection of unrelated utility methods
2. **High Fragmentation**: 19 connected components show clear separation of concerns
3. **Multiple Extraction Opportunities**: 5 high-quality clusters identified for potential extraction

### Expected Refactoring Suggestions

Based on the cluster count and StringUtils' known structure, GenEC would likely suggest extracting clusters related to:

1. **String Validation Methods**: `isEmpty()`, `isBlank()`, `isNumeric()`, etc.
2. **String Trimming/Padding**: `trim()`, `strip()`, `leftPad()`, `rightPad()`, etc.
3. **String Comparison**: `equals()`, `equalsIgnoreCase()`, `compare()`, etc.
4. **String Manipulation**: `substring()`, `remove()`, `replace()`, etc.
5. **Character Operations**: `isAlpha()`, `isAlphanumeric()`, `isWhitespace()`, etc.

Each extracted class would have higher cohesion and clearer responsibility.

## Conclusion

This analysis demonstrates that GenEC successfully:

✅ **Handles large, real-world classes** (9,222 LOC, 243 methods)
✅ **Performs efficiently** (~4 seconds for analysis)
✅ **Detects low cohesion** (LCOM5 = 0.969)
✅ **Builds comprehensive dependency graphs** (2,019 edges)
✅ **Identifies extraction opportunities** (5 ranked clusters)
✅ **Finds independent method groups** (19 connected components)

### Next Steps

To complete the refactoring:

1. **Set API Key**: Export `ANTHROPIC_API_KEY` to enable LLM generation
2. **Generate Suggestions**: Re-run GenEC to get detailed refactoring code
3. **Review Suggestions**: Examine proposed class names, method lists, and rationale
4. **Apply Refactoring**: Use `--auto-apply` to apply the best suggestion
5. **Verify**: Run tests to ensure correctness

## Running This Analysis Yourself

```bash
# Clone Apache Commons Lang
git clone https://github.com/apache/commons-lang.git
cd commons-lang

# Run GenEC
python -m genec.cli \
  --target src/main/java/org/apache/commons/lang3/StringUtils.java \
  --repo . \
  --max-suggestions 5 \
  --json > analysis_results.json

# View results
cat analysis_results.json | python -m json.tool
```

## References

- **Apache Commons Lang**: https://commons.apache.org/proper/commons-lang/
- **StringUtils Documentation**: https://commons.apache.org/proper/commons-lang/apidocs/org/apache/commons/lang3/StringUtils.html
- **GenEC Documentation**: [docs/TUTORIALS.md](../docs/TUTORIALS.md)
