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
3. LLM-Only: Sends entire class to Claude with no graph analysis.
   Upper bound of what a naive LLM approach can achieve without static analysis.

For direct comparison with JDeodorant and HECS (ISSTA 2024), we cite their
published results on their respective datasets. Direct tool-to-tool comparison
on the same dataset is left as future work due to tool availability constraints.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from evaluation.baselines.field_sharing_baseline import FieldSharingBaseline
from evaluation.baselines.llm_only_baseline import LLMOnlyBaseline
from evaluation.baselines.random_baseline import RandomBaseline

# Import BENCHMARK from run_live_evaluation
from evaluation.scripts.run_live_evaluation import BENCHMARK


def run_baseline(baseline, class_file, class_name):
    """Run a single baseline and return results."""
    try:
        start = time.time()
        suggestions = baseline.analyze(class_file)
        elapsed = time.time() - start
        return {
            "class_name": class_name,
            "status": "success",
            "suggestions_total": len(suggestions),
            "execution_time": round(elapsed, 2),
            "suggestions": [
                {
                    "name": s.proposed_class_name,
                    "members": len(s.cluster.member_names) if s.cluster else 0,
                    "member_names": s.cluster.member_names if s.cluster else [],
                    "method_count": len(s.cluster.method_signatures) if s.cluster and hasattr(s.cluster, 'method_signatures') else 0,
                    "field_count": (len(s.cluster.member_names) - len(s.cluster.method_signatures)) if s.cluster and hasattr(s.cluster, 'method_signatures') else 0,
                }
                for s in suggestions
            ],
        }
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
        print("WARNING: ANTHROPIC_API_KEY not set — skipping LLM-only baseline")

    fs_results = []
    rand_results = []
    llm_results = []

    for entry in BENCHMARK:
        class_file = str(Path(entry["repo_path"]) / entry["class_file"])
        name = entry["class_name"]

        if not Path(class_file).exists():
            print(f"  Skipping {name} — file not found")
            continue

        print(f"Running baselines on {name}...")

        fs_result = run_baseline(field_sharing, class_file, name)
        fs_results.append(fs_result)
        print(f"  Field-sharing: {fs_result.get('suggestions_total', 0)} suggestions")

        rand_result = run_baseline(random_bl, class_file, name)
        rand_results.append(rand_result)
        print(f"  Random: {rand_result.get('suggestions_total', 0)} suggestions")

        if llm_bl is not None:
            llm_result = run_baseline(llm_bl, class_file, name)
            llm_results.append(llm_result)
            print(f"  LLM-only: {llm_result.get('suggestions_total', 0)} suggestions")

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
        results["llm_only"] = {
            "total_classes": len(llm_results),
            "total_suggestions": sum(r.get("suggestions_total", 0) for r in llm_results),
            "per_class": llm_results,
        }

    out_file = output_dir / "baseline_results.json"
    out_file.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
