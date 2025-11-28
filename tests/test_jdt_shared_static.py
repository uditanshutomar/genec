"""Integration tests for the Eclipse JDT wrapper regarding shared static fields."""

from pathlib import Path
import subprocess
import pytest
from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import DependencyAnalyzer
from genec.core.jdt_code_generator import JDTCodeGenerator

JDT_JAR = Path("genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar")

@pytest.fixture(scope="session")
def ensure_jdt_wrapper_built():
    """Ensure the Eclipse JDT wrapper jar is available for tests."""
    if not JDT_JAR.exists():
        subprocess.run(
            ["mvn", "-q", "-f", "genec-jdt-wrapper/pom.xml", "package"],
            check=True,
            capture_output=True,
        )
    return JDT_JAR

SHARED_STATIC_CLASS = """\
public class SharedStaticClass {
    public static final int SHARED_CONSTANT = 42;

    public int remainingMethod() {
        return SHARED_CONSTANT;
    }

    public int extractedMethod() {
        return SHARED_CONSTANT;
    }
}
"""

def test_jdt_shared_static_field_not_moved(tmp_path, ensure_jdt_wrapper_built):
    """
    If a static field is used by both extracted and remaining methods,
    it should NOT be moved to the new class.
    """
    class_file = tmp_path / "SharedStaticClass.java"
    class_file.write_text(SHARED_STATIC_CLASS, encoding="utf-8")

    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(str(class_file))

    cluster = Cluster(
        id=1,
        member_names=["extractedMethod()"],
        member_types={
            "extractedMethod()": "method"
        },
    )

    generator = JDTCodeGenerator(timeout=30)
    generated = generator.generate(
        cluster=cluster,
        new_class_name="SharedStaticHelper",
        class_file=str(class_file),
        repo_path=str(tmp_path),
        class_deps=class_deps,
    )

    new_class = generated.new_class_code
    modified_original = generated.modified_original_code
    
    # The constant should remain in the original class
    assert "public static final int SHARED_CONSTANT = 42;" in modified_original
    
    # The constant should NOT be in the new class
    assert "public static final int SHARED_CONSTANT = 42;" not in new_class
    
    # The new class should reference the original class's constant
    # Note: This might require qualification (SharedStaticClass.SHARED_CONSTANT)
    # or if it's in the same package, just SHARED_CONSTANT might work if not moved?
    # But if it's not moved, the new class needs to access it.
    # Since they are in the same package (default package in this test), 
    # access should be fine if it's public/package-private.
    # But we want to ensure it's NOT moved.
