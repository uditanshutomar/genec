
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from genec.core.llm_interface import LLMInterface
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies

def test_prompt_construction():
    print("Testing prompt construction...")

    # Mock data
    # Mock data
    methods = ["public void validateEmail(String e)", "public boolean isValid()"]
    fields = ["private String email"]
    member_names = methods + fields
    member_types = {m: "method" for m in methods}
    member_types.update({f: "field" for f in fields})

    cluster = Cluster(id=1, member_names=member_names, member_types=member_types)
    class_deps = ClassDependencies(class_name="User", file_path="User.java", package_name="com.example")
    original_code = """
    public class User {
        private String email;
        /** Validates email */
        public void validateEmail(String e) { }
        public boolean isValid() { return true; }
    }
    """

    # Initialize interface (mock API key to avoid warning, though we won't call API)
    llm = LLMInterface(api_key="mock_key")

    # Build prompt
    prompt = llm._build_prompt(cluster, original_code, class_deps)

    # Verify key components
    checks = []

    # 1. Persona check
    checks.append(("Senior Java Architect" in prompt, "✓ Persona present", "✗ Persona missing"))

    # 2. No variable names leaked
    checks.append(("EXAMPLE_SERVICE_EXTRACTION" not in prompt, "✓ No variable names leaked", "✗ Variable name leaked"))

    # 3. Few-shot examples
    checks.append(("InputValidator" in prompt, "✓ Service extraction example present", "✗ Service example missing"))
    checks.append(("Address" in prompt, "✓ Data extraction example present", "✗ Data example missing"))

    # 4. Chain-of-thought reasoning
    checks.append(("step-by-step" in prompt.lower(), "✓ Step-by-step reasoning enforced", "✗ Reasoning enforcement missing"))

    # 5. Structured output format
    checks.append(("<reasoning>" in prompt, "✓ Reasoning tag in output format", "✗ Reasoning tag missing"))
    checks.append(("<class_name>" in prompt, "✓ Class name tag in output format", "✗ Class name tag missing"))
    checks.append(("<rationale>" in prompt, "✓ Rationale tag in output format", "✗ Rationale tag missing"))
    checks.append(("<confidence>" in prompt, "✓ Confidence tag in output format", "✗ Confidence tag missing"))

    # 6. Quality guidelines
    checks.append(("Quality Guidelines" in prompt, "✓ Quality guidelines present", "✗ Quality guidelines missing"))

    # 7. Design principles mentioned
    checks.append(("SOLID" in prompt, "✓ SOLID principles mentioned", "✗ SOLID principles missing"))
    checks.append(("Single Responsibility" in prompt, "✓ Single Responsibility Principle mentioned", "✗ SRP missing"))

    # Print results
    print("\n" + "="*60)
    print("PROMPT VERIFICATION RESULTS")
    print("="*60)

    all_passed = True
    for passed, success_msg, fail_msg in checks:
        print(success_msg if passed else fail_msg)
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n✅ All prompt checks passed!")
    else:
        print("\n❌ Some checks failed!")
        raise AssertionError("Prompt verification failed")

    print("\nGenerated Prompt Snippet:\n" + "-"*40)
    print(prompt[:500] + "...")
    print("-" * 40)

if __name__ == "__main__":
    test_prompt_construction()
