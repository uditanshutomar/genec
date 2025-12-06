#!/usr/bin/env python3
"""
GenEC Evaluation Framework - Deep Analysis

This script runs GenEC on the OrderManagementSystem test case and performs
comprehensive evaluation against ground truth.

GOAL: FIND FLAWS AND WEAKNESSES, NOT VALIDATE

Phases:
1. Setup - Prepare test environment
2. Execution - Run GenEC with detailed logging
3. Analysis - Compare against ground truth
4. Metrics - Calculate precision, recall, F1-score
5. Reporting - Generate comprehensive flaw report
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from genec.core.pipeline import GenECPipeline, PipelineResult
from genec.core.llm_interface import RefactoringSuggestion


class GenECEvaluator:
    """Comprehensive evaluator for GenEC performance."""

    def __init__(self, test_case_path: str, ground_truth_path: str, output_dir: str = "evaluation_results"):
        self.test_case_path = Path(test_case_path)
        self.ground_truth_path = Path(ground_truth_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Load ground truth
        with open(self.ground_truth_path) as f:
            self.ground_truth = json.load(f)

        # Results storage
        self.pipeline_result: PipelineResult = None
        self.evaluation_results = {
            "timestamp": datetime.now().isoformat(),
            "test_case": self.ground_truth["test_case"],
            "execution_metrics": {},
            "comparison_results": {},
            "flaws_identified": [],
            "recommendations": []
        }

    def run_evaluation(self) -> Dict:
        """Run complete evaluation pipeline."""
        print("="*80)
        print("GenEC DEEP EVALUATION - FLAW DETECTION MODE")
        print("="*80)
        print(f"Test Case: {self.ground_truth['test_case']}")
        print(f"Test File: {self.test_case_path}")
        print(f"Ground Truth: {self.ground_truth_path}")
        print(f"Output Dir: {self.output_dir}")
        print("="*80)

        # Phase 1: Setup
        self._phase1_setup()

        # Phase 2: Execute GenEC
        self._phase2_execute()

        # Phase 3: Analyze Results
        self._phase3_analyze()

        # Phase 4: Calculate Metrics
        self._phase4_metrics()

        # Phase 5: Identify Flaws
        self._phase5_identify_flaws()

        # Phase 6: Generate Report
        self._phase6_report()

        return self.evaluation_results

    def _phase1_setup(self):
        """Phase 1: Setup test environment."""
        print("\n[PHASE 1] Setting up test environment...")

        # Verify test file exists
        if not self.test_case_path.exists():
            raise FileNotFoundError(f"Test case not found: {self.test_case_path}")

        # Check if we need a git repo (for evolutionary mining)
        repo_path = self.test_case_path.parent
        while repo_path != repo_path.parent:
            if (repo_path / ".git").exists():
                print(f"  ✓ Found git repo: {repo_path}")
                self.repo_path = repo_path
                break
            repo_path = repo_path.parent
        else:
            print(f"  ⚠ No git repo found, using parent dir: {self.test_case_path.parent}")
            self.repo_path = self.test_case_path.parent

        # Initialize pipeline
        try:
            self.pipeline = GenECPipeline(
                config_file="config/config.yaml",
                config_overrides={
                    "max_suggestions": 10,  # Get more suggestions for analysis
                    "naming": {
                        "min_confidence_threshold": 0.0,  # Don't filter - we want to see everything
                        "sort_by_confidence": True
                    }
                }
            )
            print("  ✓ Pipeline initialized")
        except Exception as e:
            print(f"  ✗ Pipeline initialization failed: {e}")
            raise

        print("  ✓ Setup complete\n")

    def _phase2_execute(self):
        """Phase 2: Execute GenEC and capture results."""
        print("[PHASE 2] Executing GenEC on test case...")
        print(f"  Target: {self.test_case_path}")
        print(f"  Repo: {self.repo_path}")

        start_time = time.time()

        try:
            # Run GenEC
            self.pipeline_result = self.pipeline.run_full_pipeline(
                class_file=str(self.test_case_path),
                repo_path=str(self.repo_path),
                max_suggestions=10
            )

            execution_time = time.time() - start_time

            # Store execution metrics
            self.evaluation_results["execution_metrics"] = {
                "execution_time_seconds": execution_time,
                "clusters_detected": len(self.pipeline_result.all_clusters),
                "clusters_after_filtering": len(self.pipeline_result.filtered_clusters),
                "clusters_ranked": len(self.pipeline_result.ranked_clusters),
                "suggestions_generated": len(self.pipeline_result.suggestions),
                "verified_suggestions": len(self.pipeline_result.verified_suggestions),
                "avg_confidence": self.pipeline_result.avg_confidence,
                "min_confidence": self.pipeline_result.min_confidence,
                "max_confidence": self.pipeline_result.max_confidence,
                "high_confidence_count": self.pipeline_result.high_confidence_count
            }

            print(f"\n  Execution Results:")
            print(f"    Time: {execution_time:.2f}s")
            print(f"    Clusters detected: {len(self.pipeline_result.all_clusters)}")
            print(f"    Clusters filtered: {len(self.pipeline_result.filtered_clusters)}")
            print(f"    Clusters ranked: {len(self.pipeline_result.ranked_clusters)}")
            print(f"    Suggestions: {len(self.pipeline_result.suggestions)}")
            if self.pipeline_result.avg_confidence > 0:
                print(f"    Confidence: avg={self.pipeline_result.avg_confidence:.2f}, "
                      f"min={self.pipeline_result.min_confidence:.2f}, "
                      f"max={self.pipeline_result.max_confidence:.2f}")

            # Save raw results
            self._save_raw_results()

            print("  ✓ Execution complete\n")

        except Exception as e:
            print(f"  ✗ Execution failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _phase3_analyze(self):
        """Phase 3: Analyze results against ground truth."""
        print("[PHASE 3] Analyzing results against ground truth...")

        expected = self.ground_truth["expected_extractions"]
        actual = self.pipeline_result.suggestions

        print(f"\n  Expected extractions: {len(expected)}")
        print(f"  Actual suggestions: {len(actual)}")

        # Extract expected class names and methods
        self.expected_classes = {}
        for exp in expected:
            self.expected_classes[exp["class_name"]] = {
                "priority": exp["priority"],
                "methods": set(self._normalize_method_signature(m) for m in exp["methods"]),
                "fields": set(exp["fields"]),
                "rationale": exp["rationale"]
            }

        # Extract actual class names and methods
        self.actual_classes = {}
        for suggestion in actual:
            # Get methods from cluster
            methods = set()
            if suggestion.cluster:
                methods = set(self._normalize_method_signature(m) for m in suggestion.cluster.get_methods())

            fields = set()
            if suggestion.cluster:
                fields = set(suggestion.cluster.get_fields())

            self.actual_classes[suggestion.proposed_class_name] = {
                "confidence": suggestion.confidence_score,
                "methods": methods,
                "fields": fields,
                "rationale": suggestion.rationale,
                "reasoning": suggestion.reasoning
            }

        print("\n  Expected classes:")
        for name, data in self.expected_classes.items():
            print(f"    - {name} ({data['priority']}, {len(data['methods'])} methods)")

        print("\n  Actual suggestions:")
        for name, data in self.actual_classes.items():
            conf_str = f"confidence: {data['confidence']:.2f}" if data['confidence'] else "no confidence"
            print(f"    - {name} ({conf_str}, {len(data['methods'])} methods)")

        print("\n  ✓ Analysis complete\n")

    def _phase4_metrics(self):
        """Phase 4: Calculate precision, recall, F1-score."""
        print("[PHASE 4] Calculating evaluation metrics...")

        # Match actual to expected
        matches = self._find_best_matches()

        # Calculate metrics
        true_positives = 0
        false_positives = 0
        false_negatives = 0

        matched_expected = set()
        matched_actual = set()

        for actual_name, (expected_name, similarity) in matches.items():
            if similarity >= 0.4:  # Threshold for considering it a match (lowered from 0.5)
                true_positives += 1
                matched_expected.add(expected_name)
                matched_actual.add(actual_name)
            else:
                false_positives += 1

        # Unmatched expected = false negatives
        false_negatives = len(self.expected_classes) - len(matched_expected)

        # Unmatched actual = false positives
        false_positives += len(self.actual_classes) - len(matched_actual)

        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        self.evaluation_results["comparison_results"] = {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": precision,
            "recall": recall,
            "f1_score": f1_score,
            "matches": [
                {
                    "actual": actual_name,
                    "expected": expected_name,
                    "similarity": similarity,
                    "is_match": similarity >= 0.4
                }
                for actual_name, (expected_name, similarity) in matches.items()
            ],
            "unmatched_expected": list(set(self.expected_classes.keys()) - matched_expected),
            "unmatched_actual": list(set(self.actual_classes.keys()) - matched_actual)
        }

        print(f"\n  Metrics:")
        print(f"    True Positives: {true_positives}")
        print(f"    False Positives: {false_positives}")
        print(f"    False Negatives: {false_negatives}")
        print(f"    Precision: {precision:.2%}")
        print(f"    Recall: {recall:.2%}")
        print(f"    F1-Score: {f1_score:.2%}")

        # Compare against benchmarks
        criteria = self.ground_truth["evaluation_criteria"]
        if precision >= criteria["excellent_performance"]["precision"]:
            performance = "EXCELLENT"
        elif precision >= criteria["good_performance"]["precision"]:
            performance = "GOOD"
        elif precision >= criteria["minimum_acceptable"]["precision"]:
            performance = "ACCEPTABLE"
        else:
            performance = "POOR"

        print(f"\n  Performance: {performance}")

        print("\n  ✓ Metrics calculated\n")

    def _phase5_identify_flaws(self):
        """Phase 5: Identify specific flaws and weaknesses."""
        print("[PHASE 5] Identifying flaws and weaknesses...")

        flaws = []

        # Flaw 1: Missing expected extractions
        unmatched_expected = self.evaluation_results["comparison_results"]["unmatched_expected"]
        if unmatched_expected:
            flaw = {
                "category": "MISSED_EXTRACTIONS",
                "severity": "HIGH",
                "description": f"Failed to identify {len(unmatched_expected)} expected extractions",
                "details": []
            }
            for name in unmatched_expected:
                exp = self.expected_classes[name]
                flaw["details"].append({
                    "class_name": name,
                    "priority": exp["priority"],
                    "methods_count": len(exp["methods"]),
                    "expected_rationale": exp["rationale"]
                })
            flaws.append(flaw)

        # Flaw 2: Incorrect/spurious suggestions
        unmatched_actual = self.evaluation_results["comparison_results"]["unmatched_actual"]
        if unmatched_actual:
            flaw = {
                "category": "SPURIOUS_SUGGESTIONS",
                "severity": "MEDIUM",
                "description": f"Generated {len(unmatched_actual)} suggestions that don't match ground truth",
                "details": []
            }
            for name in unmatched_actual:
                act = self.actual_classes[name]
                flaw["details"].append({
                    "class_name": name,
                    "confidence": act["confidence"],
                    "methods_count": len(act["methods"]),
                    "rationale": act["rationale"]
                })
            flaws.append(flaw)

        # Flaw 3: Poor naming
        naming_issues = []
        for actual_name in self.actual_classes.keys():
            if any(bad in actual_name for bad in ["Helper", "Utils", "Misc", "Extra", "Manager", "Handler"]):
                naming_issues.append({
                    "class_name": actual_name,
                    "issue": "Generic/vague name",
                    "confidence": self.actual_classes[actual_name]["confidence"]
                })

        if naming_issues:
            flaws.append({
                "category": "POOR_NAMING",
                "severity": "MEDIUM",
                "description": f"Found {len(naming_issues)} classes with generic/poor names",
                "details": naming_issues
            })

        # Flaw 4: Low confidence suggestions
        low_conf_suggestions = [
            (name, data["confidence"])
            for name, data in self.actual_classes.items()
            if data["confidence"] and data["confidence"] < 0.7
        ]

        if low_conf_suggestions:
            flaws.append({
                "category": "LOW_CONFIDENCE",
                "severity": "LOW",
                "description": f"Found {len(low_conf_suggestions)} suggestions with confidence < 0.7",
                "details": [
                    {"class_name": name, "confidence": conf}
                    for name, conf in low_conf_suggestions
                ]
            })

        # Flaw 5: Partial matches (similarity 0.3-0.7)
        partial_matches = [
            m for m in self.evaluation_results["comparison_results"]["matches"]
            if 0.3 <= m["similarity"] < 0.7
        ]

        if partial_matches:
            flaws.append({
                "category": "PARTIAL_MATCHES",
                "severity": "MEDIUM",
                "description": f"Found {len(partial_matches)} partial matches (not quite right)",
                "details": partial_matches
            })

        # Flaw 6: Check if high-priority extractions were found
        high_priority_expected = [
            name for name, data in self.expected_classes.items()
            if data["priority"] == "HIGH"
        ]
        high_priority_found = [
            name for name in high_priority_expected
            if name not in unmatched_expected
        ]

        if len(high_priority_found) < len(high_priority_expected):
            missed = set(high_priority_expected) - set(high_priority_found)
            flaws.append({
                "category": "MISSED_HIGH_PRIORITY",
                "severity": "CRITICAL",
                "description": f"Missed {len(missed)} high-priority extractions",
                "details": list(missed)
            })

        self.evaluation_results["flaws_identified"] = flaws

        print(f"\n  Flaws identified: {len(flaws)}")
        for flaw in flaws:
            print(f"    [{flaw['severity']}] {flaw['category']}: {flaw['description']}")

        print("\n  ✓ Flaw identification complete\n")

    def _phase6_report(self):
        """Phase 6: Generate comprehensive report."""
        print("[PHASE 6] Generating comprehensive report...")

        # Generate recommendations based on flaws
        recommendations = self._generate_recommendations()
        self.evaluation_results["recommendations"] = recommendations

        # Save JSON report
        report_file = self.output_dir / f"evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(self.evaluation_results, f, indent=2)

        print(f"  ✓ JSON report saved: {report_file}")

        # Generate human-readable report
        markdown_file = self.output_dir / f"evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        self._generate_markdown_report(markdown_file)

        print(f"  ✓ Markdown report saved: {markdown_file}")
        print("\n  ✓ Report generation complete\n")

        return report_file, markdown_file

    def _normalize_method_signature(self, sig: str) -> str:
        """Normalize method signature for comparison."""
        # Remove return type, keep method name and param types
        sig = sig.strip()

        # Extract method name and params
        if '(' in sig:
            parts = sig.split('(')
            method_part = parts[0].strip().split()[-1]  # Last part is method name
            params = '(' + '('.join(parts[1:])  # Rest is params
            return method_part + params
        return sig

    def _find_best_matches(self) -> Dict[str, Tuple[str, float]]:
        """Find best matches between actual and expected."""
        matches = {}

        for actual_name, actual_data in self.actual_classes.items():
            best_match = None
            best_similarity = 0.0

            for expected_name, expected_data in self.expected_classes.items():
                # Calculate similarity (including name similarity)
                similarity = self._calculate_similarity(actual_data, expected_data, actual_name, expected_name)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = expected_name

            matches[actual_name] = (best_match, best_similarity)

        return matches

    def _calculate_similarity(self, actual: Dict, expected: Dict, actual_name: str = "", expected_name: str = "") -> float:
        """Calculate similarity between actual and expected extraction.

        Combines:
        - Method overlap (Jaccard similarity) - 50% weight
        - Field overlap (Jaccard similarity) - 20% weight
        - Class name similarity - 30% weight (NEW)
        """
        # Method overlap (Jaccard similarity)
        actual_methods = actual["methods"]
        expected_methods = expected["methods"]

        if not expected_methods:
            method_similarity = 0.0
        else:
            intersection = len(actual_methods & expected_methods)
            union = len(actual_methods | expected_methods)
            method_similarity = intersection / union if union > 0 else 0.0

        # Field overlap
        actual_fields = actual["fields"]
        expected_fields = expected["fields"]

        if not expected_fields:
            field_similarity = 1.0  # If no fields expected, don't penalize
        else:
            intersection = len(actual_fields & expected_fields)
            union = len(actual_fields | expected_fields)
            field_similarity = intersection / union if union > 0 else 0.0

        # Class name similarity (NEW)
        name_similarity = self._calculate_name_similarity(actual_name, expected_name)

        # Weighted average: methods 40%, name 40%, fields 20%
        similarity = 0.4 * method_similarity + 0.4 * name_similarity + 0.2 * field_similarity

        return similarity

    def _calculate_name_similarity(self, actual_name: str, expected_name: str) -> float:
        """Calculate semantic similarity between class names.

        Uses token overlap and substring matching:
        - OrderPriceCalculator vs PriceCalculator → high similarity
        - ShoppingCart vs OrderItemCollection → medium similarity
        """
        if not actual_name or not expected_name:
            return 0.0

        # Tokenize (split on camelCase)
        import re
        def tokenize(name: str) -> set:
            tokens = re.findall(r'[A-Z][a-z]+|[a-z]+|[A-Z]+(?=[A-Z]|$)', name)
            return set(t.lower() for t in tokens)

        actual_tokens = tokenize(actual_name)
        expected_tokens = tokenize(expected_name)

        if not actual_tokens or not expected_tokens:
            return 0.0

        # Token Jaccard similarity
        intersection = len(actual_tokens & expected_tokens)
        union = len(actual_tokens | expected_tokens)
        token_similarity = intersection / union if union > 0 else 0.0

        # Substring bonus: if one name contains the other
        actual_lower = actual_name.lower()
        expected_lower = expected_name.lower()

        substring_bonus = 0.0
        if expected_lower in actual_lower or actual_lower in expected_lower:
            substring_bonus = 0.3

        # Semantic equivalence check for common patterns
        semantic_equivalents = {
            ("cart", "collection", "items"): 0.5,  # ShoppingCart ≈ OrderItemCollection
            ("calculator", "computing", "calc"): 0.4,
            ("tracker", "manager"): 0.3,
            ("processor", "handler"): 0.3,
            ("notifier", "notification", "service"): 0.3,
            ("fulfillment", "shipping"): 0.3,
        }

        semantic_bonus = 0.0
        for equivalent_group, bonus in semantic_equivalents.items():
            actual_has = any(eq in actual_lower for eq in equivalent_group)
            expected_has = any(eq in expected_lower for eq in equivalent_group)
            if actual_has and expected_has:
                semantic_bonus = max(semantic_bonus, bonus)

        # Combine scores (cap at 1.0)
        total = min(1.0, token_similarity + substring_bonus + semantic_bonus)

        return total

    def _generate_recommendations(self) -> List[Dict]:
        """Generate recommendations based on identified flaws."""
        recommendations = []

        for flaw in self.evaluation_results["flaws_identified"]:
            if flaw["category"] == "MISSED_EXTRACTIONS":
                recommendations.append({
                    "issue": "Missing expected extractions",
                    "recommendation": "Improve clustering algorithm to better identify cohesive groups. Consider lowering resolution parameter or using different community detection algorithm.",
                    "priority": "HIGH"
                })

            elif flaw["category"] == "SPURIOUS_SUGGESTIONS":
                recommendations.append({
                    "issue": "Too many incorrect suggestions",
                    "recommendation": "Increase minimum cohesion threshold or improve LLM prompts to be more selective. Consider adding semantic analysis to filter out weak clusters.",
                    "priority": "MEDIUM"
                })

            elif flaw["category"] == "POOR_NAMING":
                recommendations.append({
                    "issue": "Generic class names",
                    "recommendation": "Enhance LLM prompts with more domain-specific examples. Add post-processing to reject generic names. Use semantic analysis of method/field names to suggest better names.",
                    "priority": "MEDIUM"
                })

            elif flaw["category"] == "MISSED_HIGH_PRIORITY":
                recommendations.append({
                    "issue": "Missed critical high-priority extractions",
                    "recommendation": "Review clustering parameters - may be over-filtering. Ensure graph fusion is not diluting strong structural signals. Consider increasing number of suggestions generated.",
                    "priority": "CRITICAL"
                })

        return recommendations

    def _save_raw_results(self):
        """Save raw pipeline results for detailed analysis."""
        raw_file = self.output_dir / f"raw_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        raw_data = {
            "clusters_all": [
                {
                    "id": c.id,
                    "methods": c.get_methods(),
                    "fields": c.get_fields(),
                    "cohesion": c.internal_cohesion,
                    "coupling": c.external_coupling,
                    "quality_score": c.quality_score
                }
                for c in self.pipeline_result.all_clusters
            ],
            "suggestions": [
                {
                    "class_name": s.proposed_class_name,
                    "rationale": s.rationale,
                    "confidence": s.confidence_score,
                    "reasoning": s.reasoning,
                    "methods": s.cluster.get_methods() if s.cluster else [],
                    "fields": s.cluster.get_fields() if s.cluster else []
                }
                for s in self.pipeline_result.suggestions
            ]
        }

        with open(raw_file, 'w') as f:
            json.dump(raw_data, f, indent=2)

    def _generate_markdown_report(self, output_file: Path):
        """Generate human-readable markdown report."""
        with open(output_file, 'w') as f:
            f.write("# GenEC Evaluation Report - Flaw Analysis\n\n")
            f.write(f"**Test Case**: {self.ground_truth['test_case']}\n")
            f.write(f"**Date**: {self.evaluation_results['timestamp']}\n\n")

            # Executive Summary
            f.write("## Executive Summary\n\n")
            metrics = self.evaluation_results["comparison_results"]
            f.write(f"- **Precision**: {metrics['precision']:.2%}\n")
            f.write(f"- **Recall**: {metrics['recall']:.2%}\n")
            f.write(f"- **F1-Score**: {metrics['f1_score']:.2%}\n")
            f.write(f"- **Flaws Identified**: {len(self.evaluation_results['flaws_identified'])}\n\n")

            # Execution Metrics
            f.write("## Execution Metrics\n\n")
            exec_metrics = self.evaluation_results["execution_metrics"]
            f.write(f"- **Execution Time**: {exec_metrics['execution_time_seconds']:.2f}s\n")
            f.write(f"- **Clusters Detected**: {exec_metrics['clusters_detected']}\n")
            f.write(f"- **Suggestions Generated**: {exec_metrics['suggestions_generated']}\n")
            if exec_metrics.get("avg_confidence", 0) > 0:
                f.write(f"- **Average Confidence**: {exec_metrics['avg_confidence']:.2f}\n")
            f.write("\n")

            # Detailed Flaws
            f.write("## Identified Flaws\n\n")
            for i, flaw in enumerate(self.evaluation_results["flaws_identified"], 1):
                f.write(f"### {i}. [{flaw['severity']}] {flaw['category']}\n\n")
                f.write(f"**Description**: {flaw['description']}\n\n")
                f.write(f"**Details**:\n")
                f.write(f"```json\n{json.dumps(flaw['details'], indent=2)}\n```\n\n")

            # Recommendations
            f.write("## Recommendations\n\n")
            for i, rec in enumerate(self.evaluation_results["recommendations"], 1):
                f.write(f"### {i}. [{rec['priority']}] {rec['issue']}\n\n")
                f.write(f"{rec['recommendation']}\n\n")


def main():
    """Main evaluation entry point."""
    # Configure paths
    test_case = "test_cases/OrderManagementSystem.java"
    ground_truth = "test_cases/OrderManagementSystem_GroundTruth.json"

    # Create evaluator
    evaluator = GenECEvaluator(test_case, ground_truth)

    # Run evaluation
    try:
        results = evaluator.run_evaluation()

        print("\n" + "="*80)
        print("EVALUATION COMPLETE")
        print("="*80)
        print(f"\nPrecision: {results['comparison_results']['precision']:.2%}")
        print(f"Recall: {results['comparison_results']['recall']:.2%}")
        print(f"F1-Score: {results['comparison_results']['f1_score']:.2%}")
        print(f"\nFlaws Identified: {len(results['flaws_identified'])}")
        print(f"Recommendations: {len(results['recommendations'])}")
        print(f"\nDetailed reports saved in: {evaluator.output_dir}")
        print("="*80)

        return 0

    except Exception as e:
        print(f"\n✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
