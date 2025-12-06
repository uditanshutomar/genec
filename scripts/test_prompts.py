
import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.append(os.getcwd())

from genec.core.llm_interface import LLMInterface
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies

def test_prompt_construction():
    print("Testing prompt construction...")

    # Mock dependencies
    cluster = MagicMock(spec=Cluster)
    cluster.get_methods.return_value = ["public void validateEmail(String email)", "public void validatePhone(String phone)"]
    cluster.get_fields.return_value = ["private String emailPattern"]

    class_deps = MagicMock(spec=ClassDependencies)
    class_deps.class_name = "UserManager"

    # Instantiate interface (mocking LLM to avoid API calls)
    llm = LLMInterface(api_key="dummy")
    llm._extract_javadoc_summary = MagicMock(return_value="Validates input.")

    # Build prompt
    prompt = llm._build_prompt(cluster, "original code", class_deps)

    # Verify key components
    assert "Senior Java Architect" in prompt, "Missing Persona"
    assert "FEW-SHOT EXAMPLES" in prompt, "Missing Few-Shot Header"
    assert "InputValidator" in prompt, "Missing Example 1"
    assert "Address" in prompt, "Missing Example 2"
    assert "validateEmail" in prompt, "Missing Method Context"
    assert "chain-of-thought" in prompt.lower(), "Missing CoT Instruction"

    print("SUCCESS: Prompt constructed correctly with all new components.")

if __name__ == "__main__":
    test_prompt_construction()
