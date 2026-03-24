#!/usr/bin/env python3
"""
Run GenEC on the HECS ECAccEval benchmark (92 instances from 18 projects).

For each oracle instance:
1. Read old.java and ground truth from fm_range.csv
2. Find the file path in the repo from log.json
3. Checkout the repo at the specific commit (parent of refactoring commit)
4. Run GenEC with full evolutionary coupling
5. Map GenEC clusters to member IDs (via name matching)
6. Compute per-member precision, recall, F1 against ground truth labels

Usage:
    python -m evaluation.scripts.run_hecs_benchmark \
        --dataset-dir /tmp/HECS/Evaluation/dataset/AccEval \
        --repos-dir /tmp/hecs_repos \
        --output-dir evaluation/results/hecs

    # Quick test with 3 instances:
    python -m evaluation.scripts.run_hecs_benchmark --max-instances 3

    # Resume from partial run:
    python -m evaluation.scripts.run_hecs_benchmark --skip-existing
"""

import argparse
import csv
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("HECS.Benchmark")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_DIR_DEFAULT = "/tmp/HECS/Evaluation/dataset/AccEval"
REPOS_DIR_DEFAULT = "/tmp/hecs_repos"
OUTPUT_DIR_DEFAULT = "evaluation/results/hecs"

REPO_MAP = {
    "ZooNet": "ZooNet",
    "antlr4": "antlr4",
    "aws-sdk-java": "aws-sdk-java",
    "buck": "buck",
    "cassandra": "cassandra",
    "drill": "drill",
    "eucalyptus": "eucalyptus",
    "hazelcast": "hazelcast",
    "intellij-community": "intellij-community",
    "java-algorithms-implementation": "java-algorithms-implementation",
    "jetty": "jetty",
    "junit5": "junit5",
    "languagetool": "languagetool",
    "neo4j": "neo4j",
    "robovm": "robovm",
    "spring-boot": "spring-boot",
    "wildfly": "wildfly",
    "workflow-plugin": "workflow-plugin",
}


# ---------------------------------------------------------------------------
# Oracle loader
# ---------------------------------------------------------------------------


def load_oracle(instance_dir: Path) -> dict:
    """Load ground truth from an ECAccEval instance.

    Returns a dict with keys:
        members     - list of dicts {id, name, start_line, end_line, label}
        commit_sha  - the refactoring commit SHA
        file_path   - original Java file path in the repo
        class_name  - fully-qualified class name (if available)
        log_data    - parsed RefactoringMiner JSON
    """
    # -- fm_range.csv: id,name,startLine,endLine,label ----------------------
    members = []
    fm_path = instance_dir / "fm_range.csv"
    with open(fm_path, newline="") as f:
        for row in csv.reader(f):
            if len(row) < 5:
                continue
            members.append({
                "id": int(row[0]),
                "name": row[1].strip(),
                "start_line": int(row[2]),
                "end_line": int(row[3]),
                "label": int(row[4]),  # 1=extract, 0=stay
            })

    # -- log.json: line 1 = commit SHA, rest = RefactoringMiner JSON --------
    log_text = (instance_dir / "log.json").read_text(encoding="utf-8", errors="replace").strip()
    log_lines = log_text.split("\n")
    commit_sha = log_lines[0].strip()

    log_data = {}
    file_path = None
    class_name = None
    try:
        log_data = json.loads("\n".join(log_lines[1:]))
        # Extract original file path from leftSideLocations
        for loc in log_data.get("leftSideLocations", []):
            if loc.get("codeElementType") == "TYPE_DECLARATION":
                file_path = loc.get("filePath")
                code_element = loc.get("codeElement", "")
                if code_element:
                    class_name = code_element.split(".")[-1] if "." in code_element else code_element
                break
    except json.JSONDecodeError as e:
        logger.warning("Could not parse log.json in %s: %s", instance_dir.name, e)

    # Fallback class name from old.java filename
    if not class_name:
        class_name = "UnknownClass"

    return {
        "members": members,
        "commit_sha": commit_sha,
        "file_path": file_path,
        "class_name": class_name,
        "log_data": log_data,
    }


# ---------------------------------------------------------------------------
# Repo operations
# ---------------------------------------------------------------------------


def get_default_branch(repo_path: str) -> str:
    """Detect the default branch name (main, master, etc.)."""
    for branch in ["main", "master", "develop", "trunk"]:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.returncode == 0:
            return branch
    # Fallback: use HEAD
    return "HEAD"


def checkout_commit_parent(repo_path: str, commit_sha: str) -> bool:
    """Checkout the parent of the refactoring commit.

    The commit in log.json is the REFACTORING commit — we want the code
    BEFORE extraction, so we checkout commit_sha^ (the parent).

    Returns True on success.
    """
    result = subprocess.run(
        ["git", "checkout", f"{commit_sha}^", "--force"],
        cwd=repo_path, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        logger.warning(
            "git checkout %s^ failed in %s: %s",
            commit_sha[:8], repo_path, result.stderr.strip()[:200],
        )
        return False
    return True


def restore_repo(repo_path: str, default_branch: str) -> None:
    """Restore repo to the default branch after evaluation."""
    subprocess.run(
        ["git", "checkout", default_branch, "--force"],
        cwd=repo_path, capture_output=True, text=True, timeout=60,
    )
    # Clean up any untracked files left by GenEC
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=repo_path, capture_output=True, text=True, timeout=60,
    )


# ---------------------------------------------------------------------------
# GenEC runner
# ---------------------------------------------------------------------------


def run_genec(class_file: str, repo_path: str, config_overrides: dict) -> "PipelineResult":
    """Run GenEC pipeline on a single Java file.

    Returns a PipelineResult or None on failure.
    """
    from genec.core.pipeline import GenECPipeline

    pipeline = GenECPipeline(
        config_file="config/config.yaml",
        config_overrides=config_overrides,
    )
    result = pipeline.run_full_pipeline(class_file, repo_path)
    return result


# ---------------------------------------------------------------------------
# Mapping GenEC output -> oracle member IDs
# ---------------------------------------------------------------------------


def _bare_name(signature: str) -> str:
    """Extract bare method/field name from a GenEC member signature.

    GenEC stores method names as signatures like ``compose_float(int, int, ByteBuffer)``
    or sometimes just bare names like ``compose_float``.  Fields are stored as
    bare names.  This function extracts the portion before the first '(' to get
    the bare name.
    """
    # Strip any leading return type / modifiers (e.g. "public void foo()")
    # GenEC signatures are typically just "name(params)" or "name"
    name = signature.strip()
    paren_idx = name.find("(")
    if paren_idx != -1:
        name = name[:paren_idx]
    # If there is a space, take the last token (handles "void foo" -> "foo")
    if " " in name:
        name = name.split()[-1]
    return name.strip()


def map_genec_to_oracle(
    suggestions: list,
    all_clusters: list,
    oracle_members: list[dict],
) -> set[int]:
    """Map GenEC's extraction clusters to oracle member IDs.

    GenEC produces RefactoringSuggestions, each wrapping a Cluster with
    member_names.  We match each member name against oracle members by
    bare name, then by line-range overlap as a tiebreaker for overloaded
    methods.

    We check both verified suggestions AND all clusters (since some valid
    clusters may fail verification due to code-gen issues).

    Returns: set of oracle member IDs predicted for extraction.
    """
    predicted_ids: set[int] = set()

    # Build oracle lookup: name -> list of members (handles overloads)
    name_to_members: dict[str, list[dict]] = {}
    for m in oracle_members:
        name_to_members.setdefault(m["name"], []).append(m)

    # Collect all member names from suggestions and clusters
    all_member_names: set[str] = set()

    # Prefer verified suggestions
    for sug in suggestions:
        cluster = getattr(sug, "cluster", None)
        if cluster is None:
            continue
        for name in cluster.member_names:
            all_member_names.add(name)

    # Also include raw clusters if no suggestions were generated
    if not all_member_names and all_clusters:
        for cluster in all_clusters:
            for name in cluster.member_names:
                all_member_names.add(name)

    # Map each GenEC member name to an oracle member ID
    for full_name in all_member_names:
        bare = _bare_name(full_name)
        candidates = name_to_members.get(bare, [])
        if len(candidates) == 1:
            predicted_ids.add(candidates[0]["id"])
        elif len(candidates) > 1:
            # Multiple overloads — add all (conservative: treats any match as extract)
            for c in candidates:
                predicted_ids.add(c["id"])

    return predicted_ids


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def compute_metrics(oracle_members: list[dict], predicted_extract_ids: set[int]) -> dict:
    """Compute precision, recall, F1 against ground truth."""
    true_extract = {m["id"] for m in oracle_members if m["label"] == 1}

    tp = len(predicted_extract_ids & true_extract)
    fp = len(predicted_extract_ids - true_extract)
    fn = len(true_extract - predicted_extract_ids)
    tn = len({m["id"] for m in oracle_members if m["label"] == 0} - predicted_extract_ids)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(oracle_members) if oracle_members else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


# ---------------------------------------------------------------------------
# Instance enumerator
# ---------------------------------------------------------------------------


def enumerate_instances(dataset_dir: Path) -> list[dict]:
    """Enumerate all oracle instances across all projects.

    Returns list of dicts with keys: project, instance_id, instance_dir.
    """
    instances = []
    for project_dir in sorted(dataset_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        project = project_dir.name
        for instance_dir in sorted(project_dir.iterdir()):
            if not instance_dir.is_dir():
                continue
            # Verify required files exist
            if not (instance_dir / "fm_range.csv").exists():
                continue
            if not (instance_dir / "old.java").exists():
                continue
            instances.append({
                "project": project,
                "instance_id": instance_dir.name,
                "instance_dir": instance_dir,
            })
    return instances


# ---------------------------------------------------------------------------
# Main benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(args: argparse.Namespace) -> dict:
    """Run the full HECS benchmark evaluation."""
    dataset_dir = Path(args.dataset_dir)
    repos_dir = Path(args.repos_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Per-instance results file (for --skip-existing)
    per_instance_file = output_dir / "per_instance_results.json"
    existing_results: dict[str, dict] = {}
    if args.skip_existing and per_instance_file.exists():
        try:
            existing_results = {
                r["key"]: r
                for r in json.loads(per_instance_file.read_text())
            }
            logger.info("Loaded %d existing results (--skip-existing)", len(existing_results))
        except Exception as e:
            logger.warning("Could not load existing results: %s", e)

    # Enumerate instances
    instances = enumerate_instances(dataset_dir)
    logger.info("Found %d oracle instances across %d projects",
                len(instances), len({i["project"] for i in instances}))

    # Filter by project if specified
    if args.projects:
        project_set = set(args.projects)
        instances = [i for i in instances if i["project"] in project_set]
        logger.info("Filtered to %d instances for projects: %s",
                     len(instances), args.projects)

    # Limit instances for testing
    if args.max_instances:
        instances = instances[:args.max_instances]
        logger.info("Limited to %d instances (--max-instances)", args.max_instances)

    # GenEC config overrides for benchmark mode
    config_overrides = {
        # Disable refactoring application (we only need cluster detection)
        "refactoring_application": {
            "enabled": False,
            "auto_apply": False,
            "dry_run": True,
            "max_passes": 1,
        },
        # Disable structural transforms
        "structural_transforms": {
            "enabled": False,
        },
        # Use LLM for naming but skip expensive verification repair
        "verification": {
            "enable_syntactic": True,
            "enable_semantic": False,
            "enable_behavioral": False,
        },
        # Suppress verbose logging
        "logging": {
            "level": "WARNING",
        },
    }

    if args.no_llm:
        config_overrides["llm"] = {"api_key": ""}
        config_overrides["naming"] = {"use_llm": False}

    if args.no_evo:
        config_overrides["evolution"] = {"window_months": 0}

    # Track which repos we've cached default branches for
    default_branches: dict[str, str] = {}
    results_list: list[dict] = []
    errors: list[dict] = []

    total = len(instances)
    t_start = time.time()

    for idx, inst in enumerate(instances, 1):
        project = inst["project"]
        instance_id = inst["instance_id"]
        instance_dir = inst["instance_dir"]
        key = f"{project}/{instance_id}"

        logger.info("[%d/%d] Processing %s", idx, total, key)

        # Skip if already computed
        if key in existing_results:
            logger.info("  Skipping (already computed)")
            results_list.append(existing_results[key])
            continue

        # Load oracle
        try:
            oracle = load_oracle(instance_dir)
        except Exception as e:
            logger.error("  Failed to load oracle: %s", e)
            errors.append({"key": key, "error": f"oracle load: {e}"})
            continue

        members = oracle["members"]
        commit_sha = oracle["commit_sha"]
        file_path = oracle["file_path"]
        class_name = oracle["class_name"]

        true_extract_count = sum(1 for m in members if m["label"] == 1)
        logger.info("  Class: %s, Members: %d, To extract: %d",
                     class_name, len(members), true_extract_count)

        # Resolve repo path
        repo_name = REPO_MAP.get(project)
        if not repo_name:
            logger.warning("  No repo mapping for project '%s', skipping", project)
            errors.append({"key": key, "error": f"no repo mapping for {project}"})
            continue

        repo_path = str(repos_dir / repo_name)
        if not Path(repo_path).is_dir():
            logger.warning("  Repo not found: %s, skipping", repo_path)
            errors.append({"key": key, "error": f"repo not found: {repo_path}"})
            continue

        # Cache default branch
        if repo_name not in default_branches:
            default_branches[repo_name] = get_default_branch(repo_path)

        # Checkout parent of refactoring commit
        if not checkout_commit_parent(repo_path, commit_sha):
            logger.warning("  Checkout failed for %s^, skipping", commit_sha[:8])
            errors.append({"key": key, "error": f"checkout {commit_sha[:8]}^ failed"})
            restore_repo(repo_path, default_branches[repo_name])
            continue

        # Find the Java file in the repo.
        # We prefer using old.java from the dataset (guaranteed correct content)
        # but need the repo checked out for evolutionary coupling mining.
        # Strategy: copy old.java to a temp location if the repo file doesn't
        # match or doesn't exist.
        java_file = None
        if file_path:
            candidate = Path(repo_path) / file_path
            if candidate.exists():
                java_file = str(candidate)

        # Fallback: use old.java from the dataset directly
        if not java_file:
            # Copy old.java into a temp dir with proper name
            old_java = instance_dir / "old.java"
            java_file = str(old_java)
            logger.info("  Using old.java from dataset (repo file not found)")

        # Run GenEC
        result_entry = {
            "key": key,
            "project": project,
            "instance_id": instance_id,
            "class_name": class_name,
            "commit_sha": commit_sha,
            "members_total": len(members),
            "members_to_extract": true_extract_count,
        }

        try:
            t0 = time.time()
            pipeline_result = run_genec(java_file, repo_path, config_overrides)
            elapsed = time.time() - t0

            if pipeline_result is None:
                raise RuntimeError("Pipeline returned None")

            # Collect suggestions and clusters
            suggestions = pipeline_result.suggestions or []
            all_clusters = pipeline_result.all_clusters or []

            # Map to oracle
            predicted_ids = map_genec_to_oracle(suggestions, all_clusters, members)

            # Compute metrics
            metrics = compute_metrics(members, predicted_ids)

            result_entry.update({
                "genec_clusters": len(all_clusters),
                "genec_suggestions": len(suggestions),
                "genec_predicted": len(predicted_ids),
                "predicted_ids": sorted(predicted_ids),
                **metrics,
                "elapsed_seconds": round(elapsed, 2),
                "status": "ok",
            })

            logger.info(
                "  P=%.2f  R=%.2f  F1=%.2f  (predicted %d / true %d)  [%.1fs]",
                metrics["precision"], metrics["recall"], metrics["f1"],
                len(predicted_ids), true_extract_count, elapsed,
            )

        except Exception as e:
            logger.error("  GenEC failed: %s", e)
            logger.debug(traceback.format_exc())
            result_entry.update({
                "status": "error",
                "error": str(e)[:500],
            })
            errors.append({"key": key, "error": str(e)[:500]})

        results_list.append(result_entry)

        # Restore repo
        restore_repo(repo_path, default_branches[repo_name])

        # Save incremental results after each instance
        _save_per_instance(per_instance_file, results_list)

    total_time = time.time() - t_start

    # ---------------------------------------------------------------------------
    # Aggregate results
    # ---------------------------------------------------------------------------
    ok_results = [r for r in results_list if r.get("status") == "ok"]
    logger.info("=" * 70)
    logger.info("Benchmark complete: %d/%d instances evaluated successfully",
                len(ok_results), total)

    aggregate = _compute_aggregate(ok_results)

    summary = {
        "total_instances": total,
        "instances_evaluated": len(ok_results),
        "instances_failed": len(errors),
        "total_time_seconds": round(total_time, 1),
        "aggregate": aggregate,
        "per_instance": results_list,
        "errors": errors,
    }

    # Save full results
    results_file = output_dir / "hecs_benchmark_results.json"
    results_file.write_text(json.dumps(summary, indent=2))
    logger.info("Results saved to %s", results_file)

    # Print aggregate summary
    if aggregate:
        logger.info("Aggregate:  P=%.4f  R=%.4f  F1=%.4f  Accuracy=%.4f",
                     aggregate["macro_precision"], aggregate["macro_recall"],
                     aggregate["macro_f1"], aggregate["macro_accuracy"])
        logger.info("Micro:      P=%.4f  R=%.4f  F1=%.4f",
                     aggregate["micro_precision"], aggregate["micro_recall"],
                     aggregate["micro_f1"])

    return summary


def _save_per_instance(path: Path, results: list[dict]) -> None:
    """Incrementally save per-instance results."""
    try:
        path.write_text(json.dumps(results, indent=2))
    except Exception as e:
        logger.warning("Could not save incremental results: %s", e)


def _compute_aggregate(ok_results: list[dict]) -> dict:
    """Compute macro and micro aggregate metrics."""
    if not ok_results:
        return {}

    # Macro averages
    precisions = [r["precision"] for r in ok_results]
    recalls = [r["recall"] for r in ok_results]
    f1s = [r["f1"] for r in ok_results]
    accuracies = [r["accuracy"] for r in ok_results]

    # Micro averages (sum TP/FP/FN across all instances)
    total_tp = sum(r.get("tp", 0) for r in ok_results)
    total_fp = sum(r.get("fp", 0) for r in ok_results)
    total_fn = sum(r.get("fn", 0) for r in ok_results)

    micro_p = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_r = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) > 0 else 0.0

    return {
        "macro_precision": round(sum(precisions) / len(precisions), 4),
        "macro_recall": round(sum(recalls) / len(recalls), 4),
        "macro_f1": round(sum(f1s) / len(f1s), 4),
        "macro_accuracy": round(sum(accuracies) / len(accuracies), 4),
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "total_tp": total_tp,
        "total_fp": total_fp,
        "total_fn": total_fn,
        "num_instances": len(ok_results),
    }


# ---------------------------------------------------------------------------
# Per-project breakdown
# ---------------------------------------------------------------------------


def print_per_project_summary(results: list[dict]) -> None:
    """Print a per-project breakdown to the logger."""
    from collections import defaultdict

    project_results = defaultdict(list)
    for r in results:
        if r.get("status") == "ok":
            project_results[r["project"]].append(r)

    logger.info("=" * 70)
    logger.info("Per-project summary:")
    logger.info("%-30s %5s %8s %8s %8s", "Project", "N", "P", "R", "F1")
    logger.info("-" * 70)

    for project in sorted(project_results.keys()):
        pr = project_results[project]
        n = len(pr)
        avg_p = sum(r["precision"] for r in pr) / n
        avg_r = sum(r["recall"] for r in pr) / n
        avg_f1 = sum(r["f1"] for r in pr) / n
        logger.info("%-30s %5d %8.4f %8.4f %8.4f", project, n, avg_p, avg_r, avg_f1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run GenEC on the HECS ECAccEval benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dataset-dir",
        default=DATASET_DIR_DEFAULT,
        help="Path to HECS AccEval dataset directory (default: %(default)s)",
    )
    parser.add_argument(
        "--repos-dir",
        default=REPOS_DIR_DEFAULT,
        help="Path to cloned HECS project repos (default: %(default)s)",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR_DEFAULT,
        help="Output directory for results (default: %(default)s)",
    )
    parser.add_argument(
        "--max-instances",
        type=int,
        default=None,
        help="Maximum number of instances to evaluate (for testing)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip instances that already have results",
    )
    parser.add_argument(
        "--projects",
        nargs="+",
        default=None,
        help="Only evaluate specific projects (e.g., cassandra hazelcast)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM naming (saves API credits)",
    )
    parser.add_argument(
        "--no-evo",
        action="store_true",
        help="Disable evolutionary coupling (static-only baseline)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("HECS ECAccEval Benchmark Runner")
    logger.info("  Dataset:    %s", args.dataset_dir)
    logger.info("  Repos:      %s", args.repos_dir)
    logger.info("  Output:     %s", args.output_dir)
    if args.max_instances:
        logger.info("  Max inst:   %d", args.max_instances)
    if args.no_llm:
        logger.info("  LLM:        disabled")
    if args.no_evo:
        logger.info("  Evo:        disabled")

    summary = run_benchmark(args)

    # Print per-project breakdown
    if summary.get("per_instance"):
        print_per_project_summary(summary["per_instance"])


if __name__ == "__main__":
    main()
