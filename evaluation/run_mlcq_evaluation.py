#!/usr/bin/env python3
"""
GenEC Evaluation Harness for MLCQ God Class Dataset

This script evaluates GenEC on the MLCQ dataset of expert-annotated god classes.
"""

import csv
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import tempfile
import shutil

# Add genec to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class GodClassSample:
    """A god class sample from MLCQ dataset."""
    id: int
    code_name: str
    repository: str
    commit_hash: str
    path: str
    start_line: int
    end_line: int
    severity: str
    link: str


@dataclass
class EvaluationResult:
    """Result of evaluating GenEC on a god class."""
    sample_id: int
    class_name: str
    repository: str
    clusters_detected: int
    suggestions_count: int
    verified_count: int
    avg_confidence: float
    execution_time: float
    suggested_class_names: list
    error: Optional[str] = None


def load_mlcq_godclasses(csv_path: str) -> list[GodClassSample]:
    """Load God Class samples from MLCQ CSV."""
    samples = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sample = GodClassSample(
                id=int(row['id']),
                code_name=row['code_name'],
                repository=row['repository'].replace('git@github.com:', 'https://github.com/').replace('.git', ''),
                commit_hash=row['commit_hash'],
                path=row['path'],
                start_line=int(row['start_line']),
                end_line=int(row['end_line']),
                severity=row['severity'],
                link=row['link']
            )
            samples.append(sample)
    return samples


def clone_or_checkout_repo(repo_url: str, commit_hash: str, work_dir: Path) -> Optional[Path]:
    """Clone repo or checkout specific commit."""
    repo_name = repo_url.split('/')[-1]
    repo_path = work_dir / repo_name
    
    try:
        if not repo_path.exists():
            print(f"  Cloning {repo_url}...")
            subprocess.run(
                ['git', 'clone', repo_url, str(repo_path)],
                capture_output=True, timeout=300, check=True
            )
        
        # Fetch and checkout specific commit
        subprocess.run(
            ['git', 'fetch', 'origin', commit_hash],
            cwd=repo_path, capture_output=True, timeout=60
        )
        subprocess.run(
            ['git', 'checkout', commit_hash],
            cwd=repo_path, capture_output=True, timeout=30
        )
        
        return repo_path
    except Exception as e:
        print(f"  Failed to clone/checkout: {e}")
        return None


def run_genec_on_class(class_file: Path, repo_path: Path, ablation: bool = False) -> EvaluationResult:
    """Run GenEC pipeline on a class file."""
    from genec.core.pipeline import GenECPipeline
    import time
    
    start_time = time.time()
    
    try:
        # Override config for evaluation
        overrides = {
            'verification': {
                'syntactic': {
                    'lenient_mode': True
                }
            }
        }
        
        # Apply ablation settings if enabled
        if ablation:
            print("  [ABLATION MODE] Disabling evolutionary coupling...")
            overrides['fusion'] = {'alpha': 1.0}  # 100% static weight
            overrides['evolution'] = {'window_months': 0}  # Skip mining
        
        pipeline = GenECPipeline(config_file='config/config.yaml', config_overrides=overrides)
        
        result = pipeline.run_full_pipeline(
            class_file=str(class_file),
            repo_path=str(repo_path),
            max_suggestions=5
        )
        
        execution_time = time.time() - start_time
        
        return EvaluationResult(
            sample_id=0,  # Will be set by caller
            class_name=class_file.stem,
            repository=str(repo_path),
            clusters_detected=len(result.all_clusters),
            suggestions_count=len(result.suggestions),
            verified_count=len(result.verified_suggestions),
            avg_confidence=result.avg_confidence,
            execution_time=execution_time,
            suggested_class_names=[s.proposed_class_name for s in result.suggestions[:5]]
        )
    except Exception as e:
        return EvaluationResult(
            sample_id=0,
            class_name=class_file.stem if class_file else "unknown",
            repository=str(repo_path),
            clusters_detected=0,
            suggestions_count=0,
            verified_count=0,
            avg_confidence=0.0,
            execution_time=time.time() - start_time,
            suggested_class_names=[],
            error=str(e)
        )


def evaluate_sample(sample: GodClassSample, work_dir: Path, ablation: bool = False) -> EvaluationResult:
    """Evaluate GenEC on a single MLCQ sample."""
    print(f"\nEvaluating: {sample.code_name} ({sample.severity})")
    
    # Clone/checkout repo
    repo_path = clone_or_checkout_repo(sample.repository, sample.commit_hash, work_dir)
    if not repo_path:
        return EvaluationResult(
            sample_id=sample.id,
            class_name=sample.code_name,
            repository=sample.repository,
            clusters_detected=0,
            suggestions_count=0,
            verified_count=0,
            avg_confidence=0.0,
            execution_time=0.0,
            suggested_class_names=[],
            error="Failed to clone repository"
        )
    
    # Find the class file
    class_file = repo_path / sample.path.lstrip('/')
    if not class_file.exists():
        return EvaluationResult(
            sample_id=sample.id,
            class_name=sample.code_name,
            repository=sample.repository,
            clusters_detected=0,
            suggestions_count=0,
            verified_count=0,
            avg_confidence=0.0,
            execution_time=0.0,
            suggested_class_names=[],
            error=f"File not found: {class_file}"
        )
    
    # Run GenEC
    result = run_genec_on_class(class_file, repo_path, ablation=ablation)
    result.sample_id = sample.id
    
    return result


def main():
    """Main evaluation runner."""
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description='Evaluate GenEC on MLCQ God Classes')
    parser.add_argument('--dataset', default='evaluation/datasets/mlcq_godclasses.csv',
                       help='Path to MLCQ god classes CSV')
    parser.add_argument('--max-samples', type=int, default=10,
                       help='Maximum samples to evaluate')
    parser.add_argument('--output', default='evaluation/results/mlcq_eval_results.json',
                       help='Output file for results')
    parser.add_argument('--work-dir', default='/tmp/genec_eval',
                       help='Working directory for cloning repos')
    parser.add_argument('--ablation', action='store_true',
                       help='Run in ablation mode (No Evolutionary Coupling)')
    args = parser.parse_args()
    
    # Set up API key
    if 'ANTHROPIC_API_KEY' not in os.environ:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    # Load dataset
    print(f"Loading MLCQ god classes from {args.dataset}...")
    samples = load_mlcq_godclasses(args.dataset)
    print(f"Loaded {len(samples)} god class samples")
    
    # Limit samples
    samples = samples[:args.max_samples]
    print(f"Evaluating {len(samples)} samples...")
    
    # Create work directory
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Run evaluation
    results = []
    for i, sample in enumerate(samples, 1):
        print(f"\n[{i}/{len(samples)}] Processing sample {sample.id}...")
        result = evaluate_sample(sample, work_dir, ablation=args.ablation)
        results.append(asdict(result))
        
        # Save intermediate results
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'samples_evaluated': len(results),
                'results': results
            }, f, indent=2)
    
    # Calculate summary statistics
    successful = [r for r in results if not r.get('error')]
    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total samples: {len(samples)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(samples) - len(successful)}")
    
    if successful:
        avg_clusters = sum(r['clusters_detected'] for r in successful) / len(successful)
        avg_suggestions = sum(r['suggestions_count'] for r in successful) / len(successful)
        avg_verified = sum(r['verified_count'] for r in successful) / len(successful)
        avg_confidence = sum(r['avg_confidence'] for r in successful) / len(successful)
        avg_time = sum(r['execution_time'] for r in successful) / len(successful)
        
        print(f"\nAvg clusters detected: {avg_clusters:.1f}")
        print(f"Avg suggestions: {avg_suggestions:.1f}")
        print(f"Avg verified: {avg_verified:.1f}")
        print(f"Avg confidence: {avg_confidence:.2f}")
        print(f"Avg execution time: {avg_time:.1f}s")
    
    print(f"\nResults saved to: {args.output}")


if __name__ == '__main__':
    main()
