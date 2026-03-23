#!/usr/bin/env python3
"""Generate LaTeX tables for the GenEC research paper.

Produces:
  - Table 1: RQ1 results (subject, baseline vs GenEC clusters, LCOM5, coupling)
  - Table 2: Ablation study results
  - Table 3: Verification pass rates per quality tier
  - Table 4: Ground truth match rates at different Jaccard thresholds

Usage:
    python -m evaluation.scripts.generate_latex_tables \
        --results-dir evaluation/results \
        --output-dir evaluation/results/tables
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("GenEC.LaTeX")


def _f(val, fmt=".2f"):
    """Format a number; return '--' for None / missing."""
    if val is None:
        return "--"
    try:
        return f"{float(val):{fmt}}"
    except (TypeError, ValueError):
        return "--"


# ---------------------------------------------------------------------------
# Table 1 – RQ1: GenEC vs Baseline
# ---------------------------------------------------------------------------

def generate_table_rq1(results_dir: Path) -> str:
    per_class = _load_per_class(results_dir)
    if not per_class:
        return "% No per-class data found.\n"

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{RQ1: GenEC vs.\ metric-only baseline on benchmark classes.}",
        r"\label{tab:rq1}",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Subject & \multicolumn{2}{c}{Clusters} & \multicolumn{2}{c}{LCOM5} & \multicolumn{2}{c}{Ext.\ Coupling} \\",
        r"\cmidrule(lr){2-3} \cmidrule(lr){4-5} \cmidrule(lr){6-7}",
        r" & Base & GenEC & Base & GenEC & Base & GenEC \\",
        r"\midrule",
    ]

    for cname, data in sorted(per_class.items()):
        g = data.get("genec", {})
        b = data.get("baseline", {})
        g_orig = g.get("original_metrics", {})
        b_orig = b.get("original_metrics", {})

        escaped = cname.replace("_", r"\_")
        row = (
            f"{escaped} & "
            f"{b.get('num_clusters', 0)} & {g.get('num_clusters', 0)} & "
            f"{_f(b_orig.get('lcom5'), '.3f')} & {_f(g_orig.get('lcom5'), '.3f')} & "
            f"{_f(b_orig.get('external_coupling'), '.3f')} & {_f(g_orig.get('external_coupling'), '.3f')} \\\\"
        )
        lines.append(row)

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table 2 – Ablation
# ---------------------------------------------------------------------------

def generate_table_ablation(results_dir: Path) -> str:
    ablation_file = results_dir / "ablation_results.json"
    if not ablation_file.exists():
        return "% ablation_results.json not found.\n"

    with open(ablation_file) as f:
        data = json.load(f)

    aggregate = data.get("aggregate", {})
    if not aggregate:
        return "% No aggregate ablation data.\n"

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Ablation study: contribution of each GenEC component.}",
        r"\label{tab:ablation}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Variant & Clusters & Avg LCOM5 & Avg Coupling & Verified\% & Time (s) \\",
        r"\midrule",
    ]

    label_map = {
        "full": "Full GenEC",
        "no_evo": r"$-$\,Evolutionary",
        "no_llm": r"$-$\,LLM naming",
        "no_verification": r"$-$\,Verification",
        "high_static": r"$\alpha{=}0.8$",
    }

    for vname in data.get("variants", aggregate.keys()):
        agg = aggregate.get(vname, {})
        label = label_map.get(vname, vname.replace("_", r"\_"))

        row = (
            f"{label} & "
            f"{_f(agg.get('clusters_found', {}).get('mean'), '.1f')} & "
            f"{_f(agg.get('avg_lcom5', {}).get('mean'), '.4f')} & "
            f"{_f(agg.get('avg_coupling', {}).get('mean'), '.4f')} & "
            f"{_f(agg.get('verified_pct', {}).get('mean'), '.1f')} & "
            f"{_f(agg.get('execution_time', {}).get('mean'), '.1f')} \\\\"
        )
        lines.append(row)

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table 3 – Verification pass rates per tier
# ---------------------------------------------------------------------------

def generate_table_verification(results_dir: Path) -> str:
    per_class = _load_per_class(results_dir)
    if not per_class:
        return "% No per-class data found.\n"

    tier_counts: dict[str, dict[str, int]] = {}  # tier -> {total, verified}

    for cname, data in per_class.items():
        clusters = data.get("genec", {}).get("clusters", [])
        verified_ids = set()
        for s in data.get("genec", {}).get("suggestions", []):
            verified_ids.add(s.get("cluster_id"))

        for c in clusters:
            tier = c.get("quality_tier", "unknown") or "unknown"
            if tier not in tier_counts:
                tier_counts[tier] = {"total": 0, "verified": 0}
            tier_counts[tier]["total"] += 1
            if c.get("id") in verified_ids:
                tier_counts[tier]["verified"] += 1

    if not tier_counts:
        return "% No tier data available.\n"

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Verification pass rates by quality tier.}",
        r"\label{tab:verification}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Tier & Total & Verified & Pass Rate \\",
        r"\midrule",
    ]

    tier_order = ["should", "could", "potential", "unknown"]
    for tier in tier_order:
        if tier not in tier_counts:
            continue
        tc = tier_counts[tier]
        total = tc["total"]
        verified = tc["verified"]
        rate = (verified / total * 100.0) if total > 0 else 0.0
        label = tier.capitalize()
        lines.append(f"{label} & {total} & {verified} & {_f(rate, '.1f')}\\% \\\\")

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table 4 – Ground truth match rates
# ---------------------------------------------------------------------------

def generate_table_ground_truth(results_dir: Path) -> str:
    stat_file = results_dir / "statistical_analysis.json"
    if not stat_file.exists():
        return "% statistical_analysis.json not found.\n"

    with open(stat_file) as f:
        data = json.load(f)

    gt = data.get("ground_truth", {})
    if not gt:
        return "% No ground truth data in statistical_analysis.json.\n"

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Ground truth match rates at varying Jaccard thresholds.}",
        r"\label{tab:ground_truth}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Threshold & Precision & Recall & F1 \\",
        r"\midrule",
    ]

    for key in sorted(gt.keys()):
        threshold_val = key.replace("threshold_", "")
        entry = gt[key]
        p_mean = entry.get("precision", {}).get("mean", 0.0)
        r_mean = entry.get("recall", {}).get("mean", 0.0)
        f1_mean = entry.get("f1", {}).get("mean", 0.0)
        lines.append(
            f"$J \\geq {threshold_val}$ & {_f(p_mean, '.3f')} & {_f(r_mean, '.3f')} & {_f(f1_mean, '.3f')} \\\\"
        )

    lines += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _load_per_class(results_dir: Path) -> dict[str, dict]:
    """Load per-class result JSON files."""
    skip = {"aggregate_results.json", "ablation_results.json", "statistical_analysis.json"}
    per_class = {}
    for p in sorted(results_dir.glob("*.json")):
        if p.name in skip:
            continue
        try:
            with open(p) as f:
                per_class[p.stem] = json.load(f)
        except Exception as e:
            logger.warning("Could not load %s: %s", p, e)
    return per_class


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX tables for GenEC paper.")
    parser.add_argument("--results-dir", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Output directory (default: <results-dir>/tables)")
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = args.results_dir / "tables"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "table_rq1.tex": generate_table_rq1(args.results_dir),
        "table_ablation.tex": generate_table_ablation(args.results_dir),
        "table_verification.tex": generate_table_verification(args.results_dir),
        "table_ground_truth.tex": generate_table_ground_truth(args.results_dir),
    }

    for filename, content in tables.items():
        outpath = args.output_dir / filename
        with open(outpath, "w") as f:
            f.write(content + "\n")
        logger.info("Wrote %s", outpath)

    logger.info("All tables generated in %s", args.output_dir)


if __name__ == "__main__":
    main()
