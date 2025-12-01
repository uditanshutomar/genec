
import sys
from pathlib import Path
import json
import shutil
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from genec.cli import main
from genec.core.pipeline import PipelineResult
from genec.core.cluster_detector import Cluster

def test_cli_updates():
    # Setup temp dir
    temp_dir = Path("temp_test_cli")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    # Create mock target file
    target_file = temp_dir / "Target.java"
    with open(target_file, "w") as f:
        f.write("class Target {}")

    # Create mock repo
    repo_path = temp_dir

    print("\n--- Test 1: JSON Output with Graph Data ---")

    # Mock Pipeline
    mock_pipeline = MagicMock()
    mock_result = PipelineResult(
        class_name="Target",
        original_metrics={"loc": 100},
        graph_metrics={"modularity": 0.5},
        graph_data={"nodes": [{"id": "m1"}], "edges": []},
        all_clusters=[Cluster(id=1, member_names=["m1"], internal_cohesion=0.8, external_coupling=0.2, rank_score=0.9)],
        suggestions=[]
    )
    mock_pipeline.run_full_pipeline.return_value = mock_result
    mock_pipeline.config.verification.selective_testing_enabled = True

    with patch('genec.cli.GenECPipeline', return_value=mock_pipeline):
        # Capture stdout
        from io import StringIO
        captured_output = StringIO()
        sys.stdout = captured_output

        # Run CLI
        sys.argv = ["genec", "--target", str(target_file), "--repo", str(repo_path), "--json"]
        try:
            main()
        except SystemExit:
            pass

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        try:
            data = json.loads(output)
            if "graph_data" in data and data["graph_data"]["nodes"][0]["id"] == "m1":
                print("✅ JSON output contains graph_data")
            else:
                print("❌ JSON output missing graph_data")

            if "clusters" in data and data["clusters"][0]["id"] == 1:
                print("✅ JSON output contains detailed clusters")
            else:
                print("❌ JSON output missing detailed clusters")

        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON output: {output}")

    print("\n--- Test 2: Rollback Command ---")

    # Mock RefactoringApplicator
    with patch('genec.core.refactoring_applicator.RefactoringApplicator') as MockApplicator:
        mock_app_instance = MockApplicator.return_value
        mock_app_instance.restore_latest_backup.return_value = True

        # Run CLI with --rollback
        sys.argv = ["genec", "--target", str(target_file), "--repo", str(repo_path), "--rollback", "--json"]

        captured_output = StringIO()
        sys.stdout = captured_output

        try:
            main()
        except SystemExit as e:
            if e.code == 0:
                print("✅ CLI exited with code 0")
            else:
                print(f"❌ CLI exited with code {e.code}")

        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()

        # Find JSON line
        json_line = None
        for line in output.splitlines():
            if line.strip().startswith("{"):
                json_line = line
                break

        if json_line:
            try:
                data = json.loads(json_line)
                if data["status"] == "success" and data["action"] == "rollback":
                    print("✅ Rollback command successful")
                else:
                    print(f"❌ Rollback command failed: {data}")
            except json.JSONDecodeError:
                 print(f"❌ Failed to parse JSON output: {json_line}")
        else:
            print(f"❌ No JSON output found. Output was:\n{output}")

        # Verify restore_latest_backup was called
        mock_app_instance.restore_latest_backup.assert_called_with(str(target_file.resolve()))
        print("✅ restore_latest_backup called correctly")

    # Cleanup
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_cli_updates()
