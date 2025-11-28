"""Integration tests for the Eclipse JDT wrapper regarding final fields."""

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

FINAL_FIELD_CLASS = """\
public class FinalFieldClass {
    private final int value;
    public static final String CONSTANT = "test";

    public FinalFieldClass(int start) {
        this.value = start;
    }

    public int getValue() {
        return value;
    }
    
    public String getConstant() {
        return CONSTANT;
    }
}
"""

def test_jdt_no_setter_for_final_fields(tmp_path, ensure_jdt_wrapper_built):
    """The wrapper should NOT generate setters for final fields."""
    class_file = tmp_path / "FinalFieldClass.java"
    class_file.write_text(FINAL_FIELD_CLASS, encoding="utf-8")

    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(str(class_file))

    cluster = Cluster(
        id=1,
        member_names=["getValue()", "value", "CONSTANT", "getConstant()"],
        member_types={
            "getValue()": "method",
            "value": "field",
            "CONSTANT": "field",
            "getConstant()": "method"
        },
    )

    generator = JDTCodeGenerator(timeout=30)
    generated = generator.generate(
        cluster=cluster,
        new_class_name="FinalFieldHelper",
        class_file=str(class_file),
        repo_path=str(tmp_path),
        class_deps=class_deps,
    )

    new_class = generated.new_class_code
    
    # Should have getters
    assert "public int getValue()" in new_class
    assert "public String getConstant()" in new_class
    
    # Should NOT have setters
    assert "setValue" not in new_class
    assert "setConstant" not in new_class
