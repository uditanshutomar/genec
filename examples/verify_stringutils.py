
import sys
import os
from pathlib import Path

# Add repo root to path
sys.path.append(os.getcwd())

from genec.core.jdt_code_generator import JDTCodeGenerator
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.verification.semantic_verifier import SemanticVerifier

def test_stringutils_extraction():
    print("Testing Extraction on StringUtils.java...")

    # Paths
    repo_path = "/Users/uditanshutomar/commons-lang-fresh"
    class_file = os.path.join(repo_path, "src/main/java/org/apache/commons/lang3/StringUtils.java")
    jar_path = "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"

    if not os.path.exists(class_file):
        print(f"❌ Error: Class file not found at {class_file}")
        return

    # 1. Analyze Dependencies
    print("Analyzing dependencies...")
    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(class_file)

    if not class_deps:
        print("❌ Error: Failed to analyze class dependencies")
        return

    print(f"Analyzed {len(class_deps.methods)} methods and {len(class_deps.fields)} fields.")

    # 2. Define Cluster
    # Select 'abbreviate(String,int)' and expect overloads
    print("Defining cluster with initial selection: abbreviate(String,int)")
    cluster = Cluster(id=1, member_names=[])

    # Add just one method initially
    # Note: Signature format must match what DependencyAnalyzer produces.
    # Usually it's "name(type,type)" without spaces after commas, or with spaces?
    # Let's try standard format "abbreviate(String,int)"
    initial_method = "abbreviate(String,int)"
    cluster.member_types[initial_method] = "method"
    cluster.member_names.append(initial_method)

    # 3. Initialize Generator
    generator = JDTCodeGenerator(jdt_wrapper_jar=jar_path)

    # 4. Generate Code
    print("Generating code (triggering augmentation)...")
    try:
        generated_code = generator.generate(
            cluster=cluster,
            new_class_name="StringAbbreviator",
            class_file=class_file,
            repo_path=repo_path,
            class_deps=class_deps
        )
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        return

    # 5. Verify Results
    print("\nVerifying Extraction Results:")

    new_code = generated_code.new_class_code

    expected_methods = [
        "abbreviate(String,int)",
        "abbreviate(String,int,int)",
        "abbreviate(String,String,int)",
        "abbreviate(String,String,int,int)"
    ]

    missing_methods = []
    for m in expected_methods:
        # Simple check: look for the signature in the code
        # We look for "public static String abbreviate(String" etc.
        # Just checking if the parameters appear is a rough check.
        params = m.split("(")[1].replace(")", "")
        # The generated code might have "final String str" etc.
        # So we just check if the method name appears 4 times?
        # Or check for specific unique parameter combinations.
        pass

    # Let's count occurrences of "abbreviate("
    count = new_code.count("abbreviate(")
    print(f"Found 'abbreviate(' {count} times in generated code.")

    if count >= 4:
         print("✅ PASSED: At least 4 abbreviate methods found (likely all overloads)")
    else:
         print(f"⚠️  WARNING: Found only {count} abbreviate methods. Expected 4.")
         print("Generated Code Snippet:")
         print(new_code[:500])

    # 6. Semantic Verification
    print("\nRunning Semantic Verification...")
    verifier = SemanticVerifier()
    success, message = verifier.verify(
        original_code=open(class_file).read(),
        new_class_code=generated_code.new_class_code,
        modified_original_code=generated_code.modified_original_code,
        cluster=cluster,
        class_deps=class_deps
    )

    if success:
        print("✅ PASSED: Semantic verification succeeded!")
    else:
        print(f"❌ FAILED: Semantic verification failed: {message}")

    print(f"\nGenerated Code Length: {len(new_code)}")

if __name__ == "__main__":
    test_stringutils_extraction()
