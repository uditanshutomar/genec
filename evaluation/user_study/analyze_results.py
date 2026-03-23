"""Analyze developer study results for GenEC paper."""

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats


def load_results(results_file: str) -> list[dict]:
    """Load survey results from JSON file.

    Expected format: list of dicts, each with:
    - participant_id: str
    - experience_years: int
    - role: "industry" | "phd"
    - suggestions: list of dicts with:
        - class_name: str
        - applicability: int (1-5)
        - naming: int (1-5)
        - cohesion: int (1-5)
        - quality: int (1-5)
        - naming_comparison: "genec" | "baseline" | "neither"
        - genec_name_clarity: int (1-5)
        - baseline_name_clarity: int (1-5)
    """
    with open(results_file) as f:
        return json.load(f)


def compute_likert_stats(values: list[int]) -> dict:
    """Compute statistics for Likert scale data (ordinal)."""
    arr = np.array(values)
    return {
        "n": len(arr),
        "median": float(np.median(arr)),
        "iqr": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": int(np.min(arr)),
        "max": int(np.max(arr)),
    }


def wilcoxon_test(genec_scores: list[int], baseline_scores: list[int]) -> dict:
    """Paired Wilcoxon signed-rank test for ordinal data."""
    if len(genec_scores) != len(baseline_scores):
        return {"error": "Unequal sample sizes"}

    if len(genec_scores) < 6:
        return {"warning": "Too few samples for reliable Wilcoxon test", "n": len(genec_scores)}

    try:
        stat, p_value = stats.wilcoxon(genec_scores, baseline_scores, alternative="two-sided")
        # Cliff's delta for effect size (non-parametric)
        n = len(genec_scores)
        delta = cliffs_delta(genec_scores, baseline_scores)

        return {
            "test": "Wilcoxon signed-rank",
            "statistic": float(stat),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "cliffs_delta": delta["delta"],
            "effect_size": delta["interpretation"],
            "n": n,
        }
    except ValueError as e:
        return {"error": str(e)}


def cliffs_delta(x: list, y: list) -> dict:
    """Compute Cliff's delta effect size (non-parametric)."""
    n_x, n_y = len(x), len(y)
    count = 0
    for xi in x:
        for yi in y:
            if xi > yi:
                count += 1
            elif xi < yi:
                count -= 1
    delta = count / (n_x * n_y)

    # Interpret effect size (Romano et al., 2006)
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        interpretation = "negligible"
    elif abs_delta < 0.33:
        interpretation = "small"
    elif abs_delta < 0.474:
        interpretation = "medium"
    else:
        interpretation = "large"

    return {"delta": round(delta, 3), "interpretation": interpretation}


def analyze(results: list[dict]) -> dict:
    """Full analysis of developer study results."""
    # Collect all ratings
    applicability = []
    naming = []
    cohesion = []
    quality = []
    genec_clarity = []
    baseline_clarity = []
    naming_preference = {"genec": 0, "baseline": 0, "neither": 0}

    for participant in results:
        for suggestion in participant.get("suggestions", []):
            applicability.append(suggestion["applicability"])
            naming.append(suggestion["naming"])
            cohesion.append(suggestion["cohesion"])
            quality.append(suggestion["quality"])

            pref = suggestion.get("naming_comparison", "neither")
            naming_preference[pref] = naming_preference.get(pref, 0) + 1

            if "genec_name_clarity" in suggestion:
                genec_clarity.append(suggestion["genec_name_clarity"])
            if "baseline_name_clarity" in suggestion:
                baseline_clarity.append(suggestion["baseline_name_clarity"])

    # Participant demographics
    n_industry = sum(1 for p in results if p.get("role") == "industry")
    n_phd = sum(1 for p in results if p.get("role") == "phd")
    exp_years = [p.get("experience_years", 0) for p in results]

    analysis = {
        "participants": {
            "total": len(results),
            "industry": n_industry,
            "phd": n_phd,
            "experience_mean": round(np.mean(exp_years), 1),
            "experience_range": f"{min(exp_years)}-{max(exp_years)}",
        },
        "ratings": {
            "applicability": compute_likert_stats(applicability),
            "naming": compute_likert_stats(naming),
            "cohesion": compute_likert_stats(cohesion),
            "quality": compute_likert_stats(quality),
        },
        "acceptance_rate": {
            "threshold_4": round(sum(1 for a in applicability if a >= 4) / len(applicability), 3),
            "threshold_3": round(sum(1 for a in applicability if a >= 3) / len(applicability), 3),
        },
        "naming_comparison": {
            "preference": naming_preference,
            "genec_preferred_pct": round(
                naming_preference["genec"]
                / max(sum(naming_preference.values()), 1)
                * 100,
                1,
            ),
        },
    }

    # Statistical test: GenEC naming clarity vs baseline naming clarity
    if genec_clarity and baseline_clarity and len(genec_clarity) == len(baseline_clarity):
        analysis["naming_significance"] = wilcoxon_test(genec_clarity, baseline_clarity)

    return analysis


def generate_latex_table(analysis: dict) -> str:
    """Generate LaTeX table for paper."""
    lines = [
        r"\begin{table}[t]",
        r"\caption{Developer study results (12 participants, 5-point Likert scale).}",
        r"\label{tab:developer-study}",
        r"\centering",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"\textbf{Question} & \textbf{Mean} & \textbf{SD} \\",
        r"\midrule",
    ]

    for question, key in [
        ("Would you apply this refactoring?", "applicability"),
        ("Is the class name appropriate?", "naming"),
        ("Are the method groupings cohesive?", "cohesion"),
        ("Does this improve code quality?", "quality"),
    ]:
        stats = analysis["ratings"][key]
        lines.append(f"  {question} & {stats['mean']:.1f} & {stats['std']:.1f} \\\\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Analyze GenEC developer study results")
    parser.add_argument("--results-file", required=True, help="JSON file with survey results")
    parser.add_argument("--output-file", default="evaluation/results/developer_study_analysis.json")
    parser.add_argument("--latex-output", default="evaluation/results/tables/developer_study.tex")
    args = parser.parse_args()

    results = load_results(args.results_file)
    analysis = analyze(results)

    # Save analysis
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Analysis saved to {output_path}")

    # Generate LaTeX table
    latex_path = Path(args.latex_output)
    latex_path.parent.mkdir(parents=True, exist_ok=True)
    latex = generate_latex_table(analysis)
    with open(latex_path, "w") as f:
        f.write(latex)
    print(f"LaTeX table saved to {latex_path}")

    # Print summary
    print("\n=== Developer Study Summary ===")
    print(f"Participants: {analysis['participants']['total']} "
          f"({analysis['participants']['industry']} industry, "
          f"{analysis['participants']['phd']} PhD)")
    for key in ["applicability", "naming", "cohesion", "quality"]:
        s = analysis["ratings"][key]
        print(f"  {key}: mean={s['mean']:.1f}, median={s['median']:.0f}, SD={s['std']:.1f}")
    print(f"Acceptance rate (>=4): {analysis['acceptance_rate']['threshold_4']:.0%}")
    print(f"GenEC naming preferred: {analysis['naming_comparison']['genec_preferred_pct']}%")

    if "naming_significance" in analysis:
        ns = analysis["naming_significance"]
        sig = "significant" if ns.get("significant") else "not significant"
        print(f"Naming clarity: p={ns.get('p_value', 'N/A'):.4f} ({sig}), "
              f"Cliff's d={ns.get('cliffs_delta', 'N/A')}")


if __name__ == "__main__":
    main()
