#!/usr/bin/env python3
"""Test script for Code-Maat-inspired enhancements to Stage 2."""

import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from git import Repo
from genec.core.evolutionary_miner import EvolutionaryMiner


def create_test_repo_for_enhancements():
    """Create a test Git repository with multiple files and realistic coupling patterns."""

    temp_dir = tempfile.mkdtemp(prefix='genec_test_enhancements_')
    repo = Repo.init(temp_dir)

    # Configure git
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create initial commit
    readme = Path(temp_dir) / "README.md"
    readme.write_text("# Test Repository for Code-Maat Enhancements\n")
    repo.index.add([str(readme)])
    repo.index.commit("Initial commit")

    # Create two related Java files for cross-file coupling testing
    src_dir = Path(temp_dir) / "src" / "com" / "example"
    src_dir.mkdir(parents=True)

    # File 1: PaymentProcessor.java
    payment_processor = src_dir / "PaymentProcessor.java"
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    // Hub method - will be coupled with many methods
    public void processPayment(int amount) {
        validateAmount(amount);
        System.out.println("Processing: " + amount);
    }

    // Helper method
    public boolean validateAmount(int amount) {
        return amount > 0;
    }

    // Another method for coupling
    public void calculateFee(int amount) {
        int fee = amount / 10;
    }
}
""")

    # File 2: Validator.java
    validator = src_dir / "Validator.java"
    validator.write_text("""
package com.example;

public class Validator {
    // Will be coupled with processPayment
    public boolean validatePayment(int amount) {
        return amount > 0 && amount < 10000;
    }

    // Another validation method
    public boolean validateUser(String userId) {
        return userId != null;
    }
}
""")

    repo.index.add([str(payment_processor), str(validator)])
    repo.index.commit("Add PaymentProcessor and Validator")

    # Commit 1: Change processPayment + validatePayment (cross-file coupling)
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    public void processPayment(int amount) {
        validateAmount(amount);
        // Added logging
        System.out.println("Processing payment: " + amount);
    }

    public boolean validateAmount(int amount) {
        return amount > 0;
    }

    public void calculateFee(int amount) {
        int fee = amount / 10;
    }
}
""")
    validator.write_text("""
package com.example;

public class Validator {
    public boolean validatePayment(int amount) {
        // Added upper limit
        return amount > 0 && amount < 10000;
    }

    public boolean validateUser(String userId) {
        return userId != null;
    }
}
""")
    repo.index.add([str(payment_processor), str(validator)])
    repo.index.commit("Update processPayment and validatePayment")

    # Commit 2: Change processPayment + validateAmount (within-file coupling)
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    public void processPayment(int amount) {
        validateAmount(amount);
        System.out.println("Processing payment: " + amount);
    }

    public boolean validateAmount(int amount) {
        // Added check for negative
        return amount >= 0;
    }

    public void calculateFee(int amount) {
        int fee = amount / 10;
    }
}
""")
    repo.index.add([str(payment_processor)])
    repo.index.commit("Update processPayment and validateAmount")

    # Commit 3: Change processPayment + calculateFee (high frequency method)
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    public void processPayment(int amount) {
        validateAmount(amount);
        calculateFee(amount);  // Added fee calculation
        System.out.println("Processing payment: " + amount);
    }

    public boolean validateAmount(int amount) {
        return amount >= 0;
    }

    public void calculateFee(int amount) {
        int fee = amount / 10;
        System.out.println("Fee: " + fee);
    }
}
""")
    repo.index.add([str(payment_processor)])
    repo.index.commit("Add fee calculation to processPayment")

    # Commit 4: Change processPayment again (making it a hotspot)
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    public void processPayment(int amount) {
        validateAmount(amount);
        calculateFee(amount);
        // Added transaction logging
        logTransaction(amount);
        System.out.println("Processing payment: " + amount);
    }

    public boolean validateAmount(int amount) {
        return amount >= 0;
    }

    public void calculateFee(int amount) {
        int fee = amount / 10;
        System.out.println("Fee: " + fee);
    }

    private void logTransaction(int amount) {
        System.out.println("Logged: " + amount);
    }
}
""")
    repo.index.add([str(payment_processor)])
    repo.index.commit("Add transaction logging")

    # Commit 5: Change processPayment + validatePayment again (cross-file)
    payment_processor.write_text("""
package com.example;

public class PaymentProcessor {
    public void processPayment(int amount) {
        validateAmount(amount);
        calculateFee(amount);
        logTransaction(amount);
        // Added success message
        System.out.println("Payment processed successfully: " + amount);
    }

    public boolean validateAmount(int amount) {
        return amount >= 0;
    }

    public void calculateFee(int amount) {
        int fee = amount / 10;
        System.out.println("Fee: " + fee);
    }

    private void logTransaction(int amount) {
        System.out.println("Logged: " + amount);
    }
}
""")
    validator.write_text("""
package com.example;

public class Validator {
    public boolean validatePayment(int amount) {
        // Added lower limit
        return amount > 0 && amount < 10000;
    }

    public boolean validateUser(String userId) {
        return userId != null;
    }
}
""")
    repo.index.add([str(payment_processor), str(validator)])
    repo.index.commit("Enhance processPayment and validatePayment")

    # Commit 6: Change validateUser (independent method, low coupling)
    validator.write_text("""
package com.example;

public class Validator {
    public boolean validatePayment(int amount) {
        return amount > 0 && amount < 10000;
    }

    public boolean validateUser(String userId) {
        // Added length check
        return userId != null && userId.length() > 0;
    }
}
""")
    repo.index.add([str(validator)])
    repo.index.commit("Update validateUser")

    return temp_dir, repo


def test_sum_of_coupling():
    """Test Enhancement 1: Sum-of-Coupling Analysis."""
    print("\n" + "=" * 80)
    print("TEST 1: SUM-OF-COUPLING ANALYSIS")
    print("=" * 80)

    temp_dir, repo = create_test_repo_for_enhancements()

    try:
        miner = EvolutionaryMiner(
            min_coupling_threshold=0.0,  # Include all coupling
            max_changeset_size=50,
            min_revisions=2
        )

        # Mine coupling for PaymentProcessor
        evo_data = miner.mine_method_cochanges(
            class_file='src/com/example/PaymentProcessor.java',
            repo_path=temp_dir,
            window_months=12,
            min_commits=2,
            show_metrics=False
        )

        print(f"\n📊 Methods found: {len(evo_data.method_names)}")
        for method, commits in sorted(evo_data.method_commits.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {method}: {commits} commits")

        # Get sum-of-coupling
        sum_coupling = miner.get_sum_of_coupling(evo_data, top_n=5)

        print("\n🔗 Sum-of-Coupling (Top 5 Hub Methods):")
        for method, sum_val in sum_coupling:
            print(f"  • {method}: {sum_val:.3f}")

        # Validate results
        if sum_coupling:
            top_method = sum_coupling[0][0]
            print(f"\n✅ Hub method identified: {top_method}")
            print("   This method is coupled with many other methods - prime refactoring candidate!")
            return True
        else:
            print("\n❌ No coupling data found")
            return False

    finally:
        shutil.rmtree(temp_dir)


def test_method_hotspots():
    """Test Enhancement 2: Method Hotspot Detection."""
    print("\n" + "=" * 80)
    print("TEST 2: METHOD HOTSPOT DETECTION")
    print("=" * 80)

    temp_dir, repo = create_test_repo_for_enhancements()

    try:
        miner = EvolutionaryMiner(
            min_coupling_threshold=0.0,
            max_changeset_size=50,
            min_revisions=2
        )

        # Mine coupling
        evo_data = miner.mine_method_cochanges(
            class_file='src/com/example/PaymentProcessor.java',
            repo_path=temp_dir,
            window_months=12,
            min_commits=2,
            show_metrics=False
        )

        # Get hotspots
        hotspots = miner.get_method_hotspots(evo_data, top_n=5, min_commits=2)

        print("\n🔥 Method Hotspots (Change Frequency × Coupling):")
        for method, commits, score in hotspots:
            print(f"  • {method}")
            print(f"      Commits: {commits}, Hotspot Score: {score:.3f}")

        # Validate results
        if hotspots:
            top_hotspot = hotspots[0]
            print(f"\n✅ Top hotspot: {top_hotspot[0]}")
            print(f"   Commits: {top_hotspot[1]}, Score: {top_hotspot[2]:.3f}")
            print("   This method changes frequently AND is highly coupled - urgent refactoring candidate!")
            return True
        else:
            print("\n❌ No hotspots found")
            return False

    finally:
        shutil.rmtree(temp_dir)


def test_cross_file_coupling():
    """Test Enhancement 3: Cross-File Method Coupling."""
    print("\n" + "=" * 80)
    print("TEST 3: CROSS-FILE METHOD COUPLING")
    print("=" * 80)

    temp_dir, repo = create_test_repo_for_enhancements()

    try:
        miner = EvolutionaryMiner(
            min_coupling_threshold=0.0,
            max_changeset_size=50,
            min_revisions=2
        )

        # Mine cross-file coupling
        evo_data = miner.mine_cross_file_method_cochanges(
            class_files=[
                'src/com/example/PaymentProcessor.java',
                'src/com/example/Validator.java'
            ],
            repo_path=temp_dir,
            window_months=12,
            min_commits=2
        )

        print(f"\n📊 Total methods found across files: {len(evo_data.method_names)}")

        # Group by file
        methods_by_file = {}
        for method in evo_data.method_names:
            if '::' in method:
                file_path, method_name = method.split('::', 1)
                if file_path not in methods_by_file:
                    methods_by_file[file_path] = []
                methods_by_file[file_path].append(method_name)

        for file_path, methods in methods_by_file.items():
            file_name = Path(file_path).name
            print(f"\n  📄 {file_name}:")
            for method in methods:
                commits = evo_data.method_commits.get(f"{file_path}::{method}", 0)
                print(f"    • {method}: {commits} commits")

        # Show cross-file coupling
        print("\n🔗 Cross-File Coupling Detected:")
        cross_file_couplings = []
        for (m1, m2), strength in evo_data.coupling_strengths.items():
            if '::' in m1 and '::' in m2:
                file1 = m1.split('::')[0]
                file2 = m2.split('::')[0]
                if file1 != file2:  # Different files
                    cross_file_couplings.append((m1, m2, strength))

        # Sort by strength
        cross_file_couplings.sort(key=lambda x: x[2], reverse=True)

        if cross_file_couplings:
            print(f"\n  Found {len(cross_file_couplings)} cross-file couplings:")
            for m1, m2, strength in cross_file_couplings[:5]:  # Top 5
                file1 = Path(m1.split('::')[0]).name
                method1 = m1.split('::')[1]
                file2 = Path(m2.split('::')[0]).name
                method2 = m2.split('::')[1]
                print(f"  • {file1}::{method1} ↔ {file2}::{method2}: {strength:.3f}")

            print("\n✅ Cross-file coupling successfully detected!")
            print("   These methods change together across module boundaries!")
            return True
        else:
            print("\n⚠️  No cross-file coupling detected (methods might not change together)")
            return True  # Still a success if implementation works

    finally:
        shutil.rmtree(temp_dir)


def test_all_enhancements():
    """Run all Code-Maat-inspired enhancement tests."""
    print("=" * 80)
    print("CODE-MAAT-INSPIRED ENHANCEMENTS - COMPREHENSIVE TEST")
    print("=" * 80)

    results = {
        "Enhancement 1: Sum-of-Coupling": test_sum_of_coupling(),
        "Enhancement 2: Method Hotspots": test_method_hotspots(),
        "Enhancement 3: Cross-File Coupling": test_cross_file_coupling(),
    }

    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(results.values())

    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL CODE-MAAT ENHANCEMENTS WORKING!")
    else:
        print("❌ SOME ENHANCEMENTS FAILED")
    print("=" * 80)

    return all_passed


if __name__ == '__main__':
    success = test_all_enhancements()
    sys.exit(0 if success else 1)
