#!/usr/bin/env python3
"""
Script to run RefactoringMiner and find Extract Class refactorings.
Then compare with GenEC suggestions.
"""

import subprocess
import json
import os
from pathlib import Path

RMINER_JAR = "/tmp/refactoring_miner/RefactoringMiner-3.0.4.jar"
REPOS_DIR = "/tmp/genec_eval"
OUTPUT_DIR = "/tmp/refactoring_miner/results"

# Repositories to analyze
REPOS = [
    "commons-io",
    "commons-lang", 
    "commons-collections",
]

def run_refactoring_miner(repo_path: str, output_file: str):
    """Run RefactoringMiner on a repository and save JSON output."""
    cmd = [
        "java", "-jar", RMINER_JAR,
        "-a", repo_path,  # Analyze all commits
        "-json", output_file
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result.returncode == 0

def extract_class_refactorings(json_file: str):
    """Extract only 'Extract Class' refactorings from the JSON output."""
    with open(json_file) as f:
        data = json.load(f)
    
    extract_classes = []
    for commit in data.get("commits", []):
        for ref in commit.get("refactorings", []):
            if ref.get("type") == "Extract Class":
                extract_classes.append({
                    "commit": commit.get("sha1"),
                    "url": commit.get("url"),
                    "source_class": ref.get("leftSideLocations", [{}])[0].get("filePath", ""),
                    "extracted_class": ref.get("rightSideLocations", [{}])[0].get("filePath", ""),
                    "description": ref.get("description", "")
                })
    return extract_classes

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    all_extractions = []
    
    for repo_name in REPOS:
        repo_path = os.path.join(REPOS_DIR, repo_name)
        if not os.path.exists(repo_path):
            print(f"Repository not found: {repo_path}")
            # Clone it
            clone_url = f"https://github.com/apache/{repo_name}.git"
            print(f"Cloning {clone_url}...")
            subprocess.run(["git", "clone", clone_url, repo_path], check=True)
        
        output_file = os.path.join(OUTPUT_DIR, f"{repo_name}_refactorings.json")
        
        if run_refactoring_miner(repo_path, output_file):
            extractions = extract_class_refactorings(output_file)
            print(f"Found {len(extractions)} Extract Class refactorings in {repo_name}")
            all_extractions.extend(extractions)
        else:
            print(f"Failed to analyze {repo_name}")
    
    # Save combined results
    combined_file = os.path.join(OUTPUT_DIR, "all_extract_class.json")
    with open(combined_file, "w") as f:
        json.dump(all_extractions, f, indent=2)
    
    print(f"\n=== SUMMARY ===")
    print(f"Total Extract Class refactorings found: {len(all_extractions)}")
    print(f"Results saved to: {combined_file}")
    
    # Print sample
    print("\nSample extractions:")
    for ext in all_extractions[:5]:
        print(f"  - {ext['source_class']} -> {ext['extracted_class']}")

if __name__ == "__main__":
    main()
