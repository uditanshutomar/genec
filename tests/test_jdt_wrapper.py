"""Integration tests for the Eclipse JDT wrapper."""

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


COUNTER_CLASS = """\
public class Counter {
    private int value;

    public Counter(int start) {
        this.value = start;
    }

    public void bump() {
        value++;
    }

    public int next() {
        return ++value;
    }

    public void adjust(int delta) {
        value += delta;
    }

    public int snapshot() {
        return value;
    }

    public void extractedAdd(int delta) {
        value = value + delta;
    }
}
"""


def test_jdt_generates_increment_helpers(tmp_path, ensure_jdt_wrapper_built):
    """The wrapper should rewrite increments via helper methods."""
    class_file = tmp_path / "Counter.java"
    class_file.write_text(COUNTER_CLASS, encoding="utf-8")

    analyzer = DependencyAnalyzer()
    class_deps = analyzer.analyze_class(str(class_file))

    cluster = Cluster(
        id=1,
        member_names=["extractedAdd(int)", "value"],
        member_types={
            "extractedAdd(int)": "method",
            "value": "field",
        },
    )

    generator = JDTCodeGenerator(timeout=30)
    generated = generator.generate(
        cluster=cluster,
        new_class_name="CounterHelper",
        class_file=str(class_file),
        repo_path=str(tmp_path),
        class_deps=class_deps,
    )

    new_class = generated.new_class_code
    modified_original = generated.modified_original_code

    assert "postIncrementValue()" in new_class
    assert "incrementValue()" in new_class
    assert "postDecrementValue()" in new_class or "decrementValue()" in new_class

    assert "counterHelper.postIncrementValue();" in modified_original
    assert "return counterHelper.incrementValue();" in modified_original
    assert "counterHelper.setValue(counterHelper.getValue() + delta);" in modified_original
    assert "return counterHelper.getValue();" in modified_original
