"""Integration tests for the Eclipse JDT wrapper regarding private method extraction."""

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

PRIVATE_METHOD_CLASS = """\
public class PrivateMethodClass {
    public void publicCaller() {
        privateMethod();
    }

    private void privateMethod() {
        System.out.println("private");
    }
}
"""

def test_jdt_extracted_private_method_becomes_public(tmp_path, ensure_jdt_wrapper_built):
    """
    If a private method is extracted, it should become public (or accessible)
    so the original class can delegate to it.
    """
    class_file = tmp_path / "PrivateMethodClass.java"
    class_file.write_text(PRIVATE_METHOD_CLASS, encoding="utf-8")

    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(str(class_file))

    cluster = Cluster(
        id=1,
        member_names=["privateMethod()"],
        member_types={
            "privateMethod()": "method"
        },
    )

    generator = JDTCodeGenerator(timeout=30)
    generated = generator.generate(
        cluster=cluster,
        new_class_name="PrivateMethodHelper",
        class_file=str(class_file),
        repo_path=str(tmp_path),
        class_deps=class_deps,
    )

    new_class = generated.new_class_code
    
    # The extracted method should be public
    assert "public void privateMethod()" in new_class
    assert "private void privateMethod()" not in new_class
