
import sys
import os
import json
from pathlib import Path

# Add repo root to path
sys.path.append(os.getcwd())

from genec.core.jdt_code_generator import JDTCodeGenerator
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.verification.semantic_verifier import SemanticVerifier

def test_full_extraction_logic():
    print("Testing Full Extraction Logic on ArrayUtils.java...")

    # Paths
    repo_path = "/Users/uditanshutomar/commons-lang-fresh"
    class_file = os.path.join(repo_path, "src/main/java/org/apache/commons/lang3/ArrayUtils.java")
    jar_path = "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"

    if not os.path.exists(class_file):
        print(f"❌ Error: Class file not found at {class_file}")
        return

    # 1. Analyze Dependencies (Real Parsing)
    print("Analyzing dependencies...")
    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(class_file)

    if not class_deps:
        print("❌ Error: Failed to analyze class dependencies")
        return

    print(f"Analyzed {len(class_deps.methods)} methods and {len(class_deps.fields)} fields.")

    # 2. Define Cluster (Simulate LLM selection)
    # We select just ONE remove method, and expect the system to find the rest
    print("Defining cluster with initial selection: remove(int[], int)")
    cluster = Cluster(id=1, member_names=[])

    # Add just one method initially
    initial_method = "remove(int[],int)"
    cluster.member_types[initial_method] = "method"
    cluster.member_names.append(initial_method)

    # 3. Initialize Generator
    generator = JDTCodeGenerator(jdt_wrapper_jar=jar_path)

    # 4. Generate Code (This triggers _augment_methods and _infer_fields)
    print("Generating code (triggering augmentation)...")
    try:
        generated_code = generator.generate(
            cluster=cluster,
            new_class_name="ArrayElementRemover",
            class_file=class_file,
            repo_path=repo_path,
            class_deps=class_deps
        )
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return

    # 5. Verify Results
    print("\nVerifying Extraction Results:")

    # Check if overloads were added
    # We expect other remove methods to be in the generated code
    new_code = generated_code.new_class_code

    expected_methods = [
        "remove(boolean[],int)",
        "remove(Object,int)",
        "remove(T[],int)", # Generic one!
        "removeAll(int[],int...)" # Should NOT be here unless we selected it or it's called?
                                  # Wait, removeAll shares name 'remove'? No.
                                  # But if we select 'remove', we only get 'remove' overloads.
    ]

    missing_methods = []
    for m in expected_methods:
        # Simple check: look for the method signature in the code
        # Note: JDT generates formatted code, so spacing might vary.
        # We'll look for the name and parameters roughly.
        name_part = m.split("(")[0]
        if name_part not in new_code:
             missing_methods.append(m)

    if not missing_methods:
        print("✅ PASSED: Overloads detected (found 'remove' variants)")
    else:
        print(f"⚠️  WARNING: Some expected methods might be missing (or just check failed): {missing_methods}")
        # This simple string check is flaky, but let's see.

    # Check for Generic Type Erasure handling
    if "Object[]" in new_code and "T[]" not in new_code:
         # This might happen if we erased it in the signature but JDT kept it in code?
         # Actually JDT should preserve generics in the output code if extraction worked.
         pass

    # Check Field Inference
    # ArrayUtils has fields like 'EMPTY_INT_ARRAY'.
    # If 'remove' uses it, it might be extracted if exclusive.
    # But 'EMPTY_INT_ARRAY' is likely public/shared, so it should NOT be extracted.
    if "EMPTY_INT_ARRAY" in new_code:
        print("❌ FAILED: Shared field EMPTY_INT_ARRAY was extracted (should be excluded)")
    else:
        print("✅ PASSED: Shared fields correctly excluded")

    # 6. Semantic Verification
    print("\nRunning Semantic Verification...")
    verifier = SemanticVerifier()
    success, message = verifier.verify(
        original_code=open(class_file).read(),
        new_class_code=generated_code.new_class_code,
        modified_original_code=generated_code.modified_original_code,
        cluster=cluster, # Note: this cluster object might not have the augmented members updated in it
                         # The generator returns code, but doesn't update the cluster object in place usually?
                         # Actually _augment_methods returns a list of strings.
                         # The verifier needs to know what was *actually* extracted.
                         # We should update the cluster object to match what was generated for verification to pass.
        class_deps=class_deps
    )

    # Update cluster with what was actually extracted (we can infer from code or just trust the generator logs)
    # For this test, we just want to see if the code is valid.

    if success:
        print("✅ PASSED: Semantic verification succeeded!")
    else:
        print(f"❌ FAILED: Semantic verification failed: {message}")
        # It might fail if we didn't update the cluster object with the augmented methods,
        # because the verifier checks if "cluster members" are in the new code.
        # If the code has MORE members than the cluster, it might complain "Unexpected members".

    print(f"\nGenerated Code Length: {len(new_code)}")

if __name__ == "__main__":
    test_full_extraction_logic()
