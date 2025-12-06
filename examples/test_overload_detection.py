
import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Set

# Add repo root to path
sys.path.append(os.getcwd())

from genec.core.jdt_code_generator import JDTCodeGenerator
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies, MethodInfo

def get_generator():
    jar_path = "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar"
    if not os.path.exists(jar_path):
        # Create dummy if real one doesn't exist (for testing logic only)
        with open("dummy.jar", "w") as f: f.write("dummy")
        jar_path = "dummy.jar"
    return JDTCodeGenerator(jdt_wrapper_jar=jar_path)

def create_method_info(name, signature, modifiers, body):
    return MethodInfo(
        name=name,
        signature=signature,
        return_type="void",
        modifiers=modifiers,
        parameters=[],
        start_line=1,
        end_line=10,
        body=body
    )

def test_overload_detection():
    print("Testing Overload Detection...")

    generator = get_generator()

    # Mock Cluster with one method
    cluster = Cluster(id=1, member_names=[])
    cluster.member_types["foo(int)"] = "method"
    cluster.member_names.append("foo(int)")

    # Mock ClassDependencies
    # foo(int) - selected
    # foo(String) - overload, not selected, not called
    # bar() - unrelated
    methods = [
        create_method_info("foo", "foo(int)", ["public"], ""),
        create_method_info("foo", "foo(String)", ["public"], ""),
        create_method_info("bar", "bar()", ["public"], "")
    ]

    class_deps = ClassDependencies(
        class_name="Test",
        package_name="com.example",
        file_path="Test.java",
        methods=methods,
        fields=[],
        method_calls={},
        field_accesses={}
    )

    # Run augmentation
    augmented = generator._augment_methods(cluster, class_deps)

    print(f"Augmented methods: {augmented}")

    if "foo(String)" in augmented:
        print("✅ PASSED: Overload foo(String) was added")
    else:
        print("❌ FAILED: Overload foo(String) was NOT added")

def test_package_private_detection():
    print("\nTesting Package-Private Detection...")

    generator = get_generator()

    # Mock Cluster
    cluster = Cluster(id=2, member_names=[])
    cluster.member_types["main()"] = "method"
    cluster.member_names.append("main()")

    # Mock ClassDependencies
    # main() calls helper()
    # helper() is package-private (no modifiers)
    methods = [
        create_method_info("main", "main()", ["public"], "helper();"),
        create_method_info("helper", "helper()", [], "")
    ]

    class_deps = ClassDependencies(
        class_name="Test",
        package_name="com.example",
        file_path="Test.java",
        methods=methods,
        fields=[],
        method_calls={"main()": ["helper"]},
        field_accesses={}
    )

    # Run augmentation
    augmented = generator._augment_methods(cluster, class_deps)

    print(f"Augmented methods: {augmented}")

    if "helper()" in augmented:
        print("✅ PASSED: Package-private helper() was added")
    else:
        print("❌ FAILED: Package-private helper() was NOT added")

def test_protected_exclusion():
    print("\nTesting Protected Exclusion...")

    generator = get_generator()

    # Mock Cluster
    cluster = Cluster(id=3, member_names=[])
    cluster.member_types["main()"] = "method"
    cluster.member_names.append("main()")

    # Mock ClassDependencies
    # main() calls prot()
    # prot() is protected
    methods = [
        create_method_info("main", "main()", ["public"], "prot();"),
        create_method_info("prot", "prot()", ["protected"], "")
    ]

    class_deps = ClassDependencies(
        class_name="Test",
        package_name="com.example",
        file_path="Test.java",
        methods=methods,
        fields=[],
        method_calls={"main()": ["prot"]},
        field_accesses={}
    )

    # Run augmentation
    augmented = generator._augment_methods(cluster, class_deps)

    print(f"Augmented methods: {augmented}")

    if "prot()" not in augmented:
        print("✅ PASSED: Protected prot() was NOT added")
    else:
        print("❌ FAILED: Protected prot() WAS added (unexpected)")

if __name__ == "__main__":
    test_overload_detection()
    test_package_private_detection()
    test_protected_exclusion()
