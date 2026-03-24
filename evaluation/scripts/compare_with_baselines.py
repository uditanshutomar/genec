#!/usr/bin/env python3
"""Compare GenEC results against baseline results.

Reads aggregate_results.json (GenEC) and baseline_results.json (baselines)
and prints a comparison table covering:
- Suggestion counts
- Average cluster size (methods per suggestion)
- Verification rate (GenEC vs baselines -- baselines have 0% verified
  since they produce no compilable code)
"""

import json
import sys
from pathlib import Path


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text())


def avg_cluster_size(per_class: list[dict]) -> float:
    """Average number of members per suggestion across all classes."""
    total_members = 0
    total_suggestions = 0
    for entry in per_class:
        for s in entry.get("suggestions", []):
            members = s.get("members", s.get("methods", []))
            total_members += len(members) if isinstance(members, list) else members
            total_suggestions += 1
    return round(total_members / total_suggestions, 1) if total_suggestions else 0.0


def main():
    results_dir = Path("evaluation/results")
    genec_path = results_dir / "live_evaluation" / "aggregate_results.json"
    baseline_path = results_dir / "baseline_results.json"

    genec = load_json(genec_path)
    baselines = load_json(baseline_path)

    # --- GenEC metrics ---
    genec_suggestions = genec["total_suggestions"]
    genec_verified = genec["total_verified"]
    genec_rate = genec["verification_rate"]
    genec_classes = genec["total_classes"]

    # Compute GenEC avg cluster size from per-class data (members = methods + fields)
    genec_total_members = 0
    genec_total_sug = 0
    for entry in genec["per_class"]:
        for s in entry.get("suggestions", []):
            members = s.get("members", s.get("methods", []))
            genec_total_members += len(members) if isinstance(members, list) else members
            genec_total_sug += 1
    genec_avg_size = round(genec_total_members / genec_total_sug, 1) if genec_total_sug else 0.0

    # --- Field-Sharing metrics ---
    fs = baselines.get("field_sharing", {})
    fs_suggestions = fs.get("total_suggestions", 0)
    fs_avg_size = avg_cluster_size(fs.get("per_class", []))

    # --- Random metrics ---
    rand = baselines.get("random", {})
    rand_suggestions = rand.get("total_suggestions", 0)
    rand_avg_size = avg_cluster_size(rand.get("per_class", []))

    # --- LLM-Only metrics (optional) ---
    llm = baselines.get("llm_only", {})
    llm_suggestions = llm.get("total_suggestions", 0) if llm else 0
    llm_avg_size = avg_cluster_size(llm.get("per_class", [])) if llm else 0.0

    # --- Print comparison table ---
    print("=" * 72)
    print("GenEC vs Baselines — Comparison Summary")
    print("=" * 72)
    print(f"{'':30s} {'GenEC':>10s} {'FieldShare':>10s} {'Random':>10s}", end="")
    if llm:
        print(f" {'LLM-Only':>10s}", end="")
    print()
    print("-" * 72)

    print(f"{'Classes evaluated':30s} {genec_classes:>10d} {fs.get('total_classes', 0):>10d} {rand.get('total_classes', 0):>10d}", end="")
    if llm:
        print(f" {llm.get('total_classes', 0):>10d}", end="")
    print()

    print(f"{'Total suggestions':30s} {genec_suggestions:>10d} {fs_suggestions:>10d} {rand_suggestions:>10d}", end="")
    if llm:
        print(f" {llm_suggestions:>10d}", end="")
    print()

    print(f"{'Avg members/suggestion':30s} {genec_avg_size:>10.1f} {fs_avg_size:>10.1f} {rand_avg_size:>10.1f}", end="")
    if llm:
        print(f" {llm_avg_size:>10.1f}", end="")
    print()

    print(f"{'Verified suggestions':30s} {genec_verified:>10d} {'N/A':>10s} {'N/A':>10s}", end="")
    if llm:
        print(f" {'N/A':>10s}", end="")
    print()

    print(f"{'Verification rate':30s} {genec_rate:>9.1f}% {'0.0%':>10s} {'0.0%':>10s}", end="")
    if llm:
        print(f" {'0.0%':>10s}", end="")
    print()

    print("-" * 72)
    print()

    # --- Delta analysis ---
    print("Delta Analysis:")
    fs_delta = genec_suggestions - fs_suggestions
    sign = "+" if fs_delta >= 0 else ""
    print(f"  GenEC vs Field-Sharing: {sign}{fs_delta} suggestions "
          f"({genec_suggestions} vs {fs_suggestions})")
    print(f"  GenEC avg cluster size: {genec_avg_size} members vs "
          f"Field-Sharing: {fs_avg_size} members")
    print()

    rand_delta = genec_suggestions - rand_suggestions
    sign = "+" if rand_delta >= 0 else ""
    print(f"  GenEC vs Random: {sign}{rand_delta} suggestions "
          f"({genec_suggestions} vs {rand_suggestions})")
    print(f"  Random produces many small partitions with 0% verification "
          f"(no compilation check).")
    print(f"  GenEC verification rate: {genec_rate}% vs Random: 0.0%")
    print()

    if llm:
        llm_delta = genec_suggestions - llm_suggestions
        sign = "+" if llm_delta >= 0 else ""
        print(f"  GenEC vs LLM-Only: {sign}{llm_delta} suggestions "
              f"({genec_suggestions} vs {llm_suggestions})")
        print(f"  LLM-Only avg cluster size: {llm_avg_size} members")
        print()

    print("Note: Baselines do not produce compilable code and have no")
    print("verification pipeline. Verification rate is 0% by construction.")


if __name__ == "__main__":
    main()
