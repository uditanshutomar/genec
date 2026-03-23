#!/usr/bin/env python3
"""Run baselines on the same benchmark classes as GenEC."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from evaluation.baselines.jdeodorant_baseline import JDeodorantBaseline
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
                    "methods": len(s.cluster.member_names) if s.cluster else 0,
                }
                for s in suggestions
            ],
        }
    except Exception as e:
        return {"class_name": class_name, "status": "error", "error": str(e)}


def main():
    output_dir = Path("evaluation/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    jdeodorant = JDeodorantBaseline()
    random_bl = RandomBaseline(seed=42)

    jd_results = []
    rand_results = []

    for entry in BENCHMARK:
        class_file = str(Path(entry["repo_path"]) / entry["class_file"])
        name = entry["class_name"]

        if not Path(class_file).exists():
            print(f"  Skipping {name} — file not found")
            continue

        print(f"Running baselines on {name}...")

        jd_result = run_baseline(jdeodorant, class_file, name)
        jd_results.append(jd_result)
        print(f"  JDeodorant: {jd_result.get('suggestions_total', 0)} suggestions")

        rand_result = run_baseline(random_bl, class_file, name)
        rand_results.append(rand_result)
        print(f"  Random: {rand_result.get('suggestions_total', 0)} suggestions")

    results = {
        "jdeodorant": {
            "total_classes": len(jd_results),
            "total_suggestions": sum(r.get("suggestions_total", 0) for r in jd_results),
            "per_class": jd_results,
        },
        "random": {
            "total_classes": len(rand_results),
            "total_suggestions": sum(r.get("suggestions_total", 0) for r in rand_results),
            "per_class": rand_results,
        },
    }

    out_file = output_dir / "baseline_results.json"
    out_file.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nResults saved to {out_file}")


if __name__ == "__main__":
    main()
