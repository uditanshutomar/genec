#!/usr/bin/env python3
"""
Run GenEC on parent commits of Extract Class refactorings to compare with actual developer extractions.
"""

import subprocess
import json
import os
import sys

# Add genec to path
sys.path.insert(0, '/Users/uditanshutomar/genec')

REPO_PATH = "/tmp/genec_eval/commons-io"
OUTPUT_DIR = "/tmp/refactoring_miner/genec_comparison"

# Extract Class refactorings from RefactoringMiner (main source files only, not tests)
EXTRACT_CLASS_COMMITS = [
    {
        "commit": "b901739a6779843da45a917a141cfd17114909de",
        "source_file": "src/java/org/apache/commons/io/FileUtils.java",
        "extracted": "FilenameUtils",
        "description": "Extract Class FilenameUtils from FileUtils"
    },
    {
        "commit": "55bae88d398feed4a3008ec5e97eb8b85c983b1e",
        "source_file": "src/main/java/org/apache/commons/io/IOUtils.java",
        "extracted": "Charsets",
        "description": "Extract Class Charsets from IOUtils"
    },
    {
        "commit": "a8c3027f993f5a9c9a82681a56fa6c1b1df4bcf3",
        "source_file": "src/main/java/org/apache/commons/io/ThreadMonitor.java",
        "extracted": "ThreadUtils",
        "description": "Extract Class ThreadUtils from ThreadMonitor"
    },
    {
        "commit": "431c428c4df6a7197a8703ad50f9dc5d3501130b",
        "source_file": "src/java/org/apache/commons/io/FileCleaner.java",
        "extracted": "FileCleaningTracker",
        "description": "Extract Class FileCleaningTracker from FileCleaner"
    },
    {
        "commit": "437392898ad91b3234da87d9225abadb4ca0ebad",
        "source_file": "src/main/java/org/apache/commons/io/file/CountingPathFileVisitor.java",
        "extracted": "PathCounts",
        "description": "Extract Class PathCounts from CountingPathFileVisitor"
    }
]

def checkout_parent(commit):
    """Checkout the parent of the given commit."""
    parent_cmd = f"git rev-parse {commit}^"
    result = subprocess.run(parent_cmd, shell=True, cwd=REPO_PATH, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error getting parent: {result.stderr}")
        return None
    parent = result.stdout.strip()
    
    checkout_cmd = f"git checkout {parent}"
    result = subprocess.run(checkout_cmd, shell=True, cwd=REPO_PATH, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error checking out: {result.stderr}")
        return None
    return parent

def run_genec_on_file(source_file):
    """Run GenEC on a single file and return suggestions."""
    full_path = os.path.join(REPO_PATH, source_file)
    if not os.path.exists(full_path):
        return {"error": f"File not found: {full_path}"}
    
    # Run GenEC
    cmd = [
        "python3", "-m", "genec.cli",
        "--file", full_path,
        "--output-format", "json",
        "--skip-verification"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd="/Users/uditanshutomar/genec",
            capture_output=True,
            text=True,
            timeout=180,
            env={**os.environ, "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "")}
        )
        
        if result.returncode == 0:
            # Try to parse JSON from output
            try:
                return json.loads(result.stdout)
            except:
                return {"stdout": result.stdout, "stderr": result.stderr}
        else:
            return {"error": result.stderr, "stdout": result.stdout}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout"}
    except Exception as e:
        return {"error": str(e)}

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = []
    
    for item in EXTRACT_CLASS_COMMITS:
        print(f"\n=== Processing: {item['description']} ===")
        
        # Checkout parent commit
        parent = checkout_parent(item['commit'])
        if not parent:
            results.append({**item, "parent": None, "genec_result": {"error": "Could not checkout parent"}})
            continue
        
        print(f"Checked out parent: {parent[:8]}")
        
        # Run GenEC
        print(f"Running GenEC on {item['source_file']}...")
        genec_result = run_genec_on_file(item['source_file'])
        
        results.append({
            **item,
            "parent": parent,
            "genec_result": genec_result
        })
        
        print(f"Result: {json.dumps(genec_result, indent=2)[:500]}...")
    
    # Reset to main branch
    subprocess.run("git checkout main", shell=True, cwd=REPO_PATH, capture_output=True)
    
    # Save results
    output_file = os.path.join(OUTPUT_DIR, "comparison_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n=== COMPLETED ===")
    print(f"Results saved to: {output_file}")
    
    # Print summary
    print("\n=== SUMMARY ===")
    for r in results:
        extracted = r.get('extracted', '?')
        genec = r.get('genec_result', {})
        if 'error' in genec:
            match = "ERROR"
        elif 'suggestions' in genec:
            suggestions = [s.get('class_name', '') for s in genec.get('suggestions', [])]
            match = f"Suggestions: {suggestions}"
        else:
            match = "No suggestions"
        print(f"  {r['source_file'].split('/')[-1]}: Developer={extracted}, GenEC={match}")

if __name__ == "__main__":
    main()
