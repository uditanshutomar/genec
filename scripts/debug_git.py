
import sys
import os
from datetime import datetime, timedelta
from git import Repo

def debug_git_mining(repo_path, file_path):
    print(f"Debugging git mining for {file_path} in {repo_path}")

    try:
        repo = Repo(repo_path)
        print(f"Repo active branch/commit: {repo.head.commit.hexsha}")

        end_date = datetime.now()
        start_date = end_date - timedelta(days=3650) # 10 years

        print(f"Looking for commits since: {start_date.isoformat()}")

        commits = list(repo.iter_commits(paths=file_path, since=start_date.isoformat()))
        print(f"Found {len(commits)} commits via iter_commits")

        for i, c in enumerate(commits[:5]):
            print(f"[{i}] {c.hexsha[:7]} - {c.committed_datetime}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_git_mining("/tmp/genec_eval_single/usergrid", "stack/core/src/main/java/org/apache/usergrid/batch/service/JobSchedulerService.java")
