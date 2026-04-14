#!/usr/bin/env python3
"""Run baselines on the same benchmark classes as GenEC.

Baseline Comparison Strategy
----------------------------
We compare GenEC against three baselines:

1. Field-Sharing Heuristic: Agglomerative clustering based on shared field access
   patterns (inspired by JDeodorant's Entity Placement, but simplified -- we do NOT
   claim this IS JDeodorant). This represents the structural-only approach.
2. Random Partitioning: Deterministic random grouping of methods (seed=42).
   Lower bound showing that structure matters.
3. LLM-Only: Sends entire class to Claude with no graph analysis. Claude produces
   method groupings AND generated code. This demonstrates the value of GenEC's
   constrained LLM + JDT architecture over naive end-to-end LLM refactoring.

For direct comparison with JDeodorant and HECS (ISSTA 2024), we cite their
published results on their respective datasets. Direct tool-to-tool comparison
on the same dataset is left as future work due to tool availability constraints.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from evaluation.baselines.field_sharing_baseline import FieldSharingBaseline
from evaluation.baselines.llm_only_baseline import LLMOnlyBaseline
from evaluation.baselines.random_baseline import RandomBaseline

# Import BENCHMARK from run_live_evaluation
from evaluation.scripts.run_live_evaluation import BENCHMARK


def check_compilation(java_code: str, class_name: str) -> bool:
    """Attempt to compile Java code and return whether it succeeds."""
    if not java_code.strip():
        return False
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / f"{class_name}.java"
            java_file.write_text(java_code, encoding="utf-8")
            result = subprocess.run(
                ["javac", "-nowarn", str(java_file)],
                capture_output=True, text=True, timeout=30,
                cwd=tmpdir,
            )
            return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def run_baseline(baseline, class_file, class_name, check_code=False):
    """Run a single baseline and return results."""
    try:
        start = time.time()
        suggestions = baseline.analyze(class_file)
        elapsed = time.time() - start

        suggestion_data = []
        compilable_count = 0

        for s in suggestions:
            entry = {
                "name": s.proposed_class_name,
                "members": len(s.cluster.member_names) if s.cluster else 0,
                "member_names": s.cluster.member_names if s.cluster else [],
                "method_count": len(s.cluster.method_signatures) if s.cluster and hasattr(s.cluster, 'method_signatures') else 0,
                "field_count": (len(s.cluster.member_names) - len(s.cluster.method_signatures)) if s.cluster and hasattr(s.cluster, 'method_signatures') else 0,
                "rationale": s.rationale or "",
                "confidence": s.confidence_score,
                "has_code": bool(s.new_class_code.strip()),
            }

            if check_code and s.new_class_code.strip():
                compiles = check_compilation(s.new_class_code, s.proposed_class_name)
                entry["compiles"] = compiles
                if compiles:
                    compilable_count += 1

            suggestion_data.append(entry)

        result = {
            "class_name": class_name,
            "status": "success",
            "suggestions_total": len(suggestions),
            "execution_time": round(elapsed, 2),
            "suggestions": suggestion_data,
        }
        if check_code:
            result["compilable_count"] = compilable_count
            result["compilation_rate"] = (
                round(compilable_count / len(suggestions), 3)
                if suggestions else 0.0
            )
        return result

    except Exception as e:
        return {"class_name": class_name, "status": "error", "error": str(e)}


def main():
    output_dir = Path("evaluation/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    field_sharing = FieldSharingBaseline()
    random_bl = RandomBaseline(seed=42)

    # LLM-only baseline requires an API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    llm_bl = LLMOnlyBaseline(api_key=api_key) if api_key else None
    if not api_key:
        print("WARNING: ANTHROPIC_API_KEY not set -- skipping LLM-only baseline")

    fs_results = []
    rand_results = []
    llm_results = []

    for entry in BENCHMARK:
        class_file = str(Path(entry["repo_path"]) / entry["class_file"])
        name = entry["class_name"]

        if not Path(class_file).exists():
            print(f"  Skipping {name} -- file not found")
            continue

        print(f"Running baselines on {name}...")

        fs_result = run_baseline(field_sharing, class_file, name)
        fs_results.append(fs_result)
        print(f"  Field-sharing: {fs_result.get('suggestions_total', 0)} suggestions")

        rand_result = run_baseline(random_bl, class_file, name)
        rand_results.append(rand_result)
        print(f"  Random: {rand_result.get('suggestions_total', 0)} suggestions")

        if llm_bl is not None:
            llm_result = run_baseline(llm_bl, class_file, name, check_code=True)
            llm_results.append(llm_result)
            total = llm_result.get("suggestions_total", 0)
            comp = llm_result.get("compilable_count", 0)
            print(f"  LLM-only: {total} suggestions, {comp} compilable")

    results = {
        "field_sharing": {
            "total_classes": len(fs_results),
            "total_suggestions": sum(r.get("suggestions_total", 0) for r in fs_results),
            "per_class": fs_results,
        },
        "random": {
            "total_classes": len(rand_results),
            "total_suggestions": sum(r.get("suggestions_total", 0) for r in rand_results),
            "per_class": rand_results,
        },
    }

    if llm_results:
        total_sugg = sum(r.get("suggestions_total", 0) for r in llm_results)
        total_comp = sum(r.get("compilable_count", 0) for r in llm_results)
        results["llm_only"] = {
            "total_classes": len(llm_results),
            "total_suggestions": total_sugg,
            "total_compilable": total_comp,
            "compilation_rate": round(total_comp / total_sugg, 3) if total_sugg else 0.0,
            "per_class": llm_results,
        }

    out_file = output_dir / "baseline_results.json"
    out_file.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {out_file}")

    # Print summary
    print("\n=== Baseline Summary ===")
    print(f"  Field-sharing: {results['field_sharing']['total_suggestions']} suggestions")
    print(f"  Random: {results['random']['total_suggestions']} suggestions")
    if "llm_only" in results:
        llm = results["llm_only"]
        print(f"  LLM-only: {llm['total_suggestions']} suggestions, "
              f"{llm['total_compilable']} compilable "
              f"({llm['compilation_rate']:.1%})")


if __name__ == "__main__":
    main()
