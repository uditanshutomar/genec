
import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Set

# Add repo root to path
sys.path.append(os.getcwd())

from genec.core.jdt_code_generator import JDTCodeGenerator
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo, FieldInfo

def get_generator():
    jar_path = "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
    if not os.path.exists(jar_path):
        # Create dummy if real one doesn't exist (for testing logic only)
        with open("dummy.jar", "w") as f: f.write("dummy")
        jar_path = "dummy.jar"
    return JDTCodeGenerator(jdt_wrapper_jar=jar_path)

def create_method_info(name, signature):
    return MethodInfo(
        name=name,
        signature=signature,
        return_type="void",
        modifiers=["public"],
        parameters=[],
        start_line=1,
        end_line=10,
        body=""
    )

def test_exclusive_field_extraction():
    print("Testing Exclusive Field Extraction...")

    generator = get_generator()

    # Mock Cluster
    cluster = Cluster(id=1, member_names=[])
    cluster.member_types["method1()"] = "method"
    cluster.member_names.append("method1()")

    # Mock ClassDependencies
    # method1() uses field1 (exclusive)
    # method2() uses field2 (shared)
    # method1() uses field2 (shared)
    methods = [
        create_method_info("method1", "method1()"),
        create_method_info("method2", "method2()")
    ]

    fields = [
        FieldInfo(name="field1", type="int", modifiers=["private"], line_number=1),
        FieldInfo(name="field2", type="int", modifiers=["private"], line_number=2)
    ]

    class_deps = ClassDependencies(
        class_name="Test",
        package_name="com.example",
        file_path="Test.java",
        methods=methods,
        fields=fields,
        method_calls={},
        field_accesses={
            "method1()": ["field1", "field2"],
            "method2()": ["field2"]
        }
    )

    # Run inference
    inferred_fields = generator._infer_fields(cluster, class_deps)

    print(f"Inferred fields: {inferred_fields}")

    if "field1" in inferred_fields:
        print("✅ PASSED: Exclusive field1 was extracted")
    else:
        print("❌ FAILED: Exclusive field1 was NOT extracted")

    if "field2" not in inferred_fields:
        print("✅ PASSED: Shared field2 was NOT extracted")
    else:
        print("❌ FAILED: Shared field2 WAS extracted (unexpected)")

if __name__ == "__main__":
    test_exclusive_field_extraction()
