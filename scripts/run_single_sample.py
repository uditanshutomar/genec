
import sys
import os
import json
from pathlib import Path
from dataclasses import asdict

# Add project root to path
sys.path.append(os.getcwd())

from evaluation.run_mlcq_evaluation import load_mlcq_godclasses, evaluate_sample

def run_single_sample(sample_id):
    print(f"Running GenEC on sample ID: {sample_id}")

    # Load dataset
    samples = load_mlcq_godclasses("evaluation/datasets/mlcq_samples.csv")
    target_sample = next((s for s in samples if s.id == sample_id), None)

    if not target_sample:
        print(f"Error: Sample {sample_id} not found.")
        return

    print(f"Found sample: {target_sample.code_name}")

    # Create work directory
    work_dir = Path("/tmp/genec_eval_single")
    work_dir.mkdir(parents=True, exist_ok=True)

    # Run evaluation
    result = evaluate_sample(target_sample, work_dir)

    # Print results
    print("\n" + "="*50)
    print("EVALUATION RESULT")
    print("="*50)
    print(json.dumps(asdict(result), indent=2))

    # Print suggestions details if any
    if result.suggested_class_names:
        print("\nSuggestions:")
        for name in result.suggested_class_names:
            print(f"- {name}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 run_single_sample.py <sample_id>")
        sys.exit(1)

    run_single_sample(int(sys.argv[1]))
