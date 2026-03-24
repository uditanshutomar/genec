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

def _load_baseline(results_dir: Path) -> dict[str, dict]:
    """Load baseline results keyed by class name."""
    baseline_file = results_dir / "baseline_results.json"
    if not baseline_file.exists():
        baseline_file = results_dir.parent / "baseline_results.json"
    if not baseline_file.exists():
        return {}
    with open(baseline_file) as f:
        baseline_data = json.load(f)
    # Use field_sharing as the structural baseline (NOT random, which
    # would overwrite due to dict key collision)
    baseline_per_class: dict[str, dict] = {}
    fs_data = baseline_data.get("field_sharing", {})
    for entry in fs_data.get("per_class", []):
        cname = entry.get("class_name", "")
        if cname:
            baseline_per_class[cname] = entry
    return baseline_per_class


def generate_table_rq1(results_dir: Path) -> str:
    per_class = _load_per_class(results_dir)
    if not per_class:
        return "% No per-class data found.\n"

    baseline_per_class = _load_baseline(results_dir)

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{GenEC vs.\ field-sharing baseline: suggestions and verification.}",
        r"\label{tab:rq1}",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"Subject & \multicolumn{2}{c}{Suggestions} & \multicolumn{2}{c}{Verified} & LCOM5 \\",
        r"\cmidrule(lr){2-3} \cmidrule(lr){4-5}",
        r" & FS & GenEC & GenEC & Rate & (orig) \\",
        r"\midrule",
    ]

    total_fs = 0
    total_genec = 0
    total_verified = 0

    for cname, data in sorted(per_class.items()):
        g_orig = data.get("original_metrics", {})
        b = baseline_per_class.get(cname, {})
        suggestions = data.get("suggestions", [])
        verified = [s for s in suggestions if s.get("verified")]

        fs_count = b.get("suggestions_total", 0)
        genec_count = len(suggestions)
        ver_count = len(verified)
        ver_rate = round(ver_count / max(genec_count, 1) * 100, 1)

        total_fs += fs_count
        total_genec += genec_count
        total_verified += ver_count

        escaped = cname.replace("_", r"\_").replace("$", r"\$")
        row = (
            f"{escaped} & "
            f"{fs_count} & {genec_count} & "
            f"{ver_count} & {ver_rate}\\% & "
            f"{_f(g_orig.get('lcom5'), '.3f')} \\\\"
        )
        lines.append(row)

    # Totals row
    total_rate = round(total_verified / max(total_genec, 1) * 100, 1)
    lines.append(r"\midrule")
    lines.append(
        f"\\textbf{{Total}} & {total_fs} & {total_genec} & "
        f"{total_verified} & {total_rate}\\% & -- \\\\"
    )

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
        r"Variant & Clusters & Avg Cohesion & Avg Coupling & Verified\% & Time (s) \\",
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
            f"{_f(agg.get('avg_cohesion', {}).get('mean'), '.4f')} & "
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
        # Flat format: suggestions are at top level and contain quality_tier directly
        suggestions = data.get("suggestions", [])

        for s in suggestions:
            tier = s.get("quality_tier", "unknown") or "unknown"
            if tier not in tier_counts:
                tier_counts[tier] = {"total": 0, "verified": 0}
            tier_counts[tier]["total"] += 1
            if s.get("verified", False):
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
    skip = {"aggregate_results.json", "ablation_results.json", "statistical_analysis.json",
            "ground_truth_analysis.json", "baseline_results.json"}
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
