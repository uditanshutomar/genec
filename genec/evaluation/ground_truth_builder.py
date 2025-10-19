"""Ground truth builder using RefactoringMiner."""

import json
import subprocess
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, field

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractClassRefactoring:
    """Represents a ground truth Extract Class refactoring."""
    commit_sha: str
    source_class: str
    extracted_class: str
    extracted_members: List[str] = field(default_factory=list)
    source_file: str = ""
    extracted_file: str = ""


class GroundTruthBuilder:
    """Builds ground truth dataset using RefactoringMiner."""

    def __init__(self, refactoring_miner_jar: Optional[str] = None):
        """
        Initialize ground truth builder.

        Args:
            refactoring_miner_jar: Path to RefactoringMiner JAR file
        """
        self.refactoring_miner_jar = refactoring_miner_jar
        self.logger = get_logger(self.__class__.__name__)

    def extract_from_repository(
        self,
        repo_path: str,
        output_file: str,
        branch: str = 'main'
    ) -> List[ExtractClassRefactoring]:
        """
        Extract Extract Class refactorings from a repository using RefactoringMiner.

        Args:
            repo_path: Path to Git repository
            output_file: Path to save JSON output
            branch: Git branch to analyze

        Returns:
            List of ExtractClassRefactoring objects
        """
        self.logger.info(f"Extracting refactorings from {repo_path}")

        if not self.refactoring_miner_jar:
            self.logger.warning("RefactoringMiner JAR not provided, using manual extraction")
            return self._manual_extraction(repo_path, output_file)

        # Run RefactoringMiner
        try:
            cmd = [
                'java',
                '-jar',
                self.refactoring_miner_jar,
                '-a',
                repo_path,
                '-json',
                output_file
            ]

            self.logger.info(f"Running RefactoringMiner: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout
            )

            if result.returncode != 0:
                self.logger.error(f"RefactoringMiner failed: {result.stderr}")
                return []

            # Parse output
            refactorings = self._parse_refactoring_miner_output(output_file)

            self.logger.info(f"Found {len(refactorings)} Extract Class refactorings")

            return refactorings

        except FileNotFoundError:
            self.logger.error("Java or RefactoringMiner JAR not found")
            return []
        except subprocess.TimeoutExpired:
            self.logger.error("RefactoringMiner timeout")
            return []
        except Exception as e:
            self.logger.error(f"Error running RefactoringMiner: {e}")
            return []

    def _parse_refactoring_miner_output(
        self,
        json_file: str
    ) -> List[ExtractClassRefactoring]:
        """
        Parse RefactoringMiner JSON output.

        Args:
            json_file: Path to JSON file

        Returns:
            List of ExtractClassRefactoring objects
        """
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)

            refactorings = []

            # Parse commits
            for commit in data.get('commits', []):
                commit_sha = commit.get('sha1', '')

                # Look for Extract Class refactorings
                for refactoring in commit.get('refactorings', []):
                    ref_type = refactoring.get('type', '')

                    if ref_type == 'Extract Class':
                        # Extract details
                        source_class = refactoring.get('sourceClass', '')
                        extracted_class = refactoring.get('extractedClass', '')

                        # Extract member list if available
                        extracted_members = []
                        for member in refactoring.get('extractedMembers', []):
                            extracted_members.append(member.get('name', ''))

                        ref_obj = ExtractClassRefactoring(
                            commit_sha=commit_sha,
                            source_class=source_class,
                            extracted_class=extracted_class,
                            extracted_members=extracted_members,
                            source_file=refactoring.get('sourceFile', ''),
                            extracted_file=refactoring.get('extractedFile', '')
                        )

                        refactorings.append(ref_obj)

            return refactorings

        except Exception as e:
            self.logger.error(f"Error parsing RefactoringMiner output: {e}")
            return []

    def _manual_extraction(
        self,
        repo_path: str,
        output_file: str
    ) -> List[ExtractClassRefactoring]:
        """
        Manual extraction placeholder (for when RefactoringMiner is not available).

        In a real implementation, this would use Git history analysis
        to heuristically detect Extract Class refactorings.

        Args:
            repo_path: Path to repository
            output_file: Output file path

        Returns:
            Empty list (placeholder)
        """
        self.logger.warning("Manual extraction not implemented")

        # Save empty dataset
        with open(output_file, 'w') as f:
            json.dump({'commits': []}, f)

        return []

    def save_ground_truth(
        self,
        refactorings: List[ExtractClassRefactoring],
        output_file: str
    ):
        """
        Save ground truth refactorings to JSON file.

        Args:
            refactorings: List of refactorings
            output_file: Output file path
        """
        data = {
            'refactorings': [
                {
                    'commit_sha': r.commit_sha,
                    'source_class': r.source_class,
                    'extracted_class': r.extracted_class,
                    'extracted_members': r.extracted_members,
                    'source_file': r.source_file,
                    'extracted_file': r.extracted_file
                }
                for r in refactorings
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        self.logger.info(f"Saved {len(refactorings)} refactorings to {output_file}")

    def load_ground_truth(self, input_file: str) -> List[ExtractClassRefactoring]:
        """
        Load ground truth refactorings from JSON file.

        Args:
            input_file: Input file path

        Returns:
            List of ExtractClassRefactoring objects
        """
        try:
            with open(input_file, 'r') as f:
                data = json.load(f)

            refactorings = []
            for item in data.get('refactorings', []):
                ref = ExtractClassRefactoring(
                    commit_sha=item['commit_sha'],
                    source_class=item['source_class'],
                    extracted_class=item['extracted_class'],
                    extracted_members=item.get('extracted_members', []),
                    source_file=item.get('source_file', ''),
                    extracted_file=item.get('extracted_file', '')
                )
                refactorings.append(ref)

            self.logger.info(f"Loaded {len(refactorings)} refactorings from {input_file}")

            return refactorings

        except Exception as e:
            self.logger.error(f"Error loading ground truth: {e}")
            return []
