
import sys
import os
import json
from pathlib import Path
from dataclasses import asdict

# Add project root to path
sys.path.append(os.getcwd())

from genec.core.pipeline import GenECPipeline

def run_local_repo(repo_path, relative_file_path):
    print(f"Running GenEC on local repo: {repo_path}")
    print(f"File: {relative_file_path}")

    repo_path = Path(repo_path).resolve()
    class_file = (repo_path / relative_file_path).resolve()

    if not class_file.exists():
        print(f"Error: File not found: {class_file}")
        return

    # Initialize pipeline
    overrides = {
        'verification': {
            'syntactic': {
                'lenient_mode': True
            }
        },
        'fusion': {
            'alpha': 0.8  # Ensure we use the new alpha
        },
        'evolution': {
            'window_months': 240, # Ensure we use the new window
            'min_revisions': 1,
            'min_coupling_threshold': 0.1
        }
    }

    pipeline = GenECPipeline(config_file='config/config.yaml', config_overrides=overrides)

    try:
        result = pipeline.run_full_pipeline(
            class_file=str(class_file),
            repo_path=str(repo_path),
            max_suggestions=5
        )

        print("\n" + "="*50)
        print("EVALUATION RESULT")
        print("="*50)
        print(f"Clusters: {len(result.all_clusters)}")
        print(f"Suggestions: {len(result.suggestions)}")
        print(f"Verified: {len(result.verified_suggestions)}")

        if result.suggestions:
            print("\nSuggestions:")
            for s in result.suggestions:
                print(f"- {s.proposed_class_name} (Conf: {s.confidence})")

    except Exception as e:
        print(f"Error running pipeline: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 run_local_repo.py <repo_path> <relative_file_path>")
        sys.exit(1)

    run_local_repo(sys.argv[1], sys.argv[2])
