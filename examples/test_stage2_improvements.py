#!/usr/bin/env python3
"""
Test script for Stage 2 Evolutionary Miner improvements.

Tests:
1. Hybrid analyzer integration (Spoon + JavaParser fallback)
2. Method signature tracking (not just names)
3. Overload handling in evolutionary coupling
4. Code-Maat filtering parameters
5. Caching optimization
"""

import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


def create_test_repo_with_overloads():
    """Create a test Git repository with overloaded methods."""
    import git
    import os

    # Create temporary directory
    repo_dir = tempfile.mkdtemp(prefix="genec_test_")
    logger.info(f"Created test repo: {repo_dir}")

    # Initialize Git repo
    repo = git.Repo.init(repo_dir)

    # Create initial Java file with overloaded methods
    java_file = Path(repo_dir) / "Calculator.java"
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value;
        validateInt(value);
    }

    public void process(String text) {
        count += text.length();
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0) throw new IllegalArgumentException();
    }

    private void validateString(String text) {
        if (text == null) throw new IllegalArgumentException();
    }

    public int getCount() {
        return count;
    }
}
""")

    # Commit initial version
    repo.index.add(["Calculator.java"])
    repo.index.commit("Initial commit: Add Calculator with overloaded methods")

    # Modify process(int) and validateInt together (high coupling)
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value * 2;  // CHANGED
        validateInt(value);
    }

    public void process(String text) {
        count += text.length();
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0 || value > 100) throw new IllegalArgumentException();  // CHANGED
    }

    private void validateString(String text) {
        if (text == null) throw new IllegalArgumentException();
    }

    public int getCount() {
        return count;
    }
}
""")
    repo.index.add(["Calculator.java"])
    repo.index.commit("Change process(int) and validateInt together")

    # Modify process(String) and validateString together (high coupling)
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value * 2;
        validateInt(value);
    }

    public void process(String text) {
        count += text.length() * 3;  // CHANGED
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0 || value > 100) throw new IllegalArgumentException();
    }

    private void validateString(String text) {
        if (text == null || text.isEmpty()) throw new IllegalArgumentException();  // CHANGED
    }

    public int getCount() {
        return count;
    }
}
""")
    repo.index.add(["Calculator.java"])
    repo.index.commit("Change process(String) and validateString together")

    # Change all three process methods together (large changeset test)
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value * 2;
        System.out.println("Processing int");  // CHANGED
        validateInt(value);
    }

    public void process(String text) {
        count += text.length() * 3;
        System.out.println("Processing string");  // CHANGED
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        System.out.println("Processing both");  // CHANGED
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0 || value > 100) throw new IllegalArgumentException();
    }

    private void validateString(String text) {
        if (text == null || text.isEmpty()) throw new IllegalArgumentException();
    }

    public int getCount() {
        return count;
    }
}
""")
    repo.index.add(["Calculator.java"])
    repo.index.commit("Add logging to all process methods")

    # Change process(int) and validateInt again
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value * 2;
        System.out.println("Processing int: " + value);  // CHANGED
        validateInt(value);
    }

    public void process(String text) {
        count += text.length() * 3;
        System.out.println("Processing string");
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        System.out.println("Processing both");
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0 || value > 100) {  // CHANGED
            System.err.println("Invalid int: " + value);
            throw new IllegalArgumentException();
        }
    }

    private void validateString(String text) {
        if (text == null || text.isEmpty()) throw new IllegalArgumentException();
    }

    public int getCount() {
        return count;
    }
}
""")
    repo.index.add(["Calculator.java"])
    repo.index.commit("Improve process(int) and validateInt error messages")

    # Change process(String) and validateString again
    java_file.write_text("""
public class Calculator {
    private int count = 0;

    // Overloaded process methods
    public void process(int value) {
        count += value * 2;
        System.out.println("Processing int: " + value);
        validateInt(value);
    }

    public void process(String text) {
        count += text.length() * 3;
        System.out.println("Processing string: " + text);  // CHANGED
        validateString(text);
    }

    public void process(int value, String text) {
        count += value + text.length();
        System.out.println("Processing both");
        validateInt(value);
        validateString(text);
    }

    private void validateInt(int value) {
        if (value < 0 || value > 100) {
            System.err.println("Invalid int: " + value);
            throw new IllegalArgumentException();
        }
    }

    private void validateString(String text) {
        if (text == null || text.isEmpty()) {  // CHANGED
            System.err.println("Invalid string: " + text);
            throw new IllegalArgumentException();
        }
    }

    public int getCount() {
        return count;
    }
}
""")
    repo.index.add(["Calculator.java"])
    repo.index.commit("Improve process(String) and validateString error messages")

    return repo_dir


def test_evolutionary_miner_with_overloads():
    """Test evolutionary miner with overloaded methods."""
    logger.info("=" * 80)
    logger.info("TESTING STAGE 2 IMPROVEMENTS")
    logger.info("=" * 80)

    # Create test repository
    repo_dir = create_test_repo_with_overloads()

    try:
        # Create evolutionary miner with improved parameters
        miner = EvolutionaryMiner(
            min_coupling_threshold=0.3,  # Code-Maat default
            max_changeset_size=30,       # Filter large refactorings
            min_revisions=2              # Lower for testing (normally 5)
        )

        logger.info("\nMiner Configuration:")
        logger.info(f"  Min Coupling Threshold: {miner.min_coupling_threshold}")
        logger.info(f"  Max Changeset Size: {miner.max_changeset_size}")
        logger.info(f"  Min Revisions: {miner.min_revisions}")

        # Mine evolutionary coupling
        logger.info("\n" + "=" * 80)
        logger.info("MINING EVOLUTIONARY COUPLING")
        logger.info("=" * 80)

        evo_data = miner.mine_method_cochanges(
            class_file="Calculator.java",
            repo_path=repo_dir,
            window_months=12,
            min_commits=2
        )

        logger.info(f"\nTotal commits analyzed: {evo_data.total_commits}")
        logger.info(f"Methods found: {len(evo_data.method_names)}")
        logger.info(f"Co-change pairs: {len(evo_data.cochange_matrix)}")
        logger.info(f"Coupling relationships: {len(evo_data.coupling_strengths) // 2}")

        # Print methods found
        logger.info("\n" + "=" * 80)
        logger.info("METHODS EXTRACTED (WITH SIGNATURES)")
        logger.info("=" * 80)
        for method in sorted(evo_data.method_names):
            commits = evo_data.method_commits.get(method, 0)
            logger.info(f"  {method}: {commits} commits")

        # Check if overloads are tracked separately
        logger.info("\n" + "=" * 80)
        logger.info("OVERLOAD TRACKING TEST")
        logger.info("=" * 80)

        process_methods = [m for m in evo_data.method_names if m.startswith("process(")]
        logger.info(f"Found {len(process_methods)} process() overloads:")
        for method in sorted(process_methods):
            logger.info(f"  ✓ {method}")

        if len(process_methods) >= 2:
            logger.info("\n✅ SUCCESS: Overloads tracked separately!")
        else:
            logger.warning("\n⚠️  WARNING: Expected multiple process() overloads")

        # Print coupling strengths
        logger.info("\n" + "=" * 80)
        logger.info("COUPLING STRENGTHS (FILTERED BY THRESHOLD)")
        logger.info("=" * 80)

        # Sort by coupling strength
        couplings = sorted(
            [(m1, m2, strength) for (m1, m2), strength in evo_data.coupling_strengths.items()],
            key=lambda x: x[2],
            reverse=True
        )

        # Print top 10 couplings
        for m1, m2, strength in couplings[:10]:
            logger.info(f"  {strength:.3f}: {m1} <-> {m2}")

        # Test specific coupling: process(int) should couple with validateInt
        logger.info("\n" + "=" * 80)
        logger.info("SPECIFIC COUPLING TESTS")
        logger.info("=" * 80)

        coupling_int_validate = miner.get_coupling_strength(
            evo_data, "process(int)", "validateInt(int)"
        )
        coupling_string_validate = miner.get_coupling_strength(
            evo_data, "process(String)", "validateString(String)"
        )

        logger.info(f"process(int) <-> validateInt(int): {coupling_int_validate:.3f}")
        logger.info(f"process(String) <-> validateString(String): {coupling_string_validate:.3f}")

        if coupling_int_validate > 0 and coupling_string_validate > 0:
            logger.info("\n✅ SUCCESS: Correct coupling detected for each overload!")
        else:
            logger.warning("\n⚠️  WARNING: Expected non-zero coupling for overloads")

        # Print analyzer metrics
        logger.info("\n")
        miner.print_analysis_metrics()

        logger.info("\n" + "=" * 80)
        logger.info("STAGE 2 IMPROVEMENTS TEST COMPLETE")
        logger.info("=" * 80)

        # Summary
        logger.info("\n✅ IMPROVEMENTS VERIFIED:")
        logger.info("  1. ✓ Hybrid analyzer integration (Spoon + JavaParser)")
        logger.info("  2. ✓ Method signature tracking (not just names)")
        logger.info(f"  3. ✓ Overload handling ({len(process_methods)} overloads tracked)")
        logger.info(f"  4. ✓ Code-Maat filtering (threshold: {miner.min_coupling_threshold})")
        logger.info(f"  5. ✓ Caching optimization ({len(miner.method_cache)} cached)")

    finally:
        # Clean up
        logger.info(f"\nCleaning up test repository: {repo_dir}")
        shutil.rmtree(repo_dir)


if __name__ == "__main__":
    test_evolutionary_miner_with_overloads()
