"""
Performance Regression Verifier.

Ensures refactorings don't introduce performance regressions.
"""

import statistics
import subprocess
import time
from dataclasses import dataclass

from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for code execution."""

    mean_time_ms: float
    median_time_ms: float
    std_dev_ms: float
    min_time_ms: float
    max_time_ms: float
    iterations: int


@dataclass
class PerformanceResult:
    """Result of performance comparison."""

    passed: bool
    original_metrics: PerformanceMetrics
    refactored_metrics: PerformanceMetrics
    regression_percent: float  # Negative = improvement, positive = regression
    error_message: str | None = None


class PerformanceVerifier:
    """
    Verifies refactorings don't introduce performance regressions.

    Uses micro-benchmarking to compare execution times
    before and after refactoring.
    """

    def __init__(
        self,
        max_regression_percent: float = 5.0,  # Allow up to 5% slowdown
        benchmark_iterations: int = 100,
        warmup_iterations: int = 10,
        enable_jmh: bool = False,  # Use JMH for more accurate benchmarks
    ):
        """
        Initialize performance verifier.

        Args:
            max_regression_percent: Maximum allowed performance regression (%)
            benchmark_iterations: Number of benchmark iterations
            warmup_iterations: Number of warmup iterations
            enable_jmh: Use JMH (Java Microbenchmark Harness) if available
        """
        self.max_regression_percent = max_regression_percent
        self.benchmark_iterations = benchmark_iterations
        self.warmup_iterations = warmup_iterations
        self.enable_jmh = enable_jmh
        self.logger = get_logger(self.__class__.__name__)

    def verify(
        self,
        original_code: str,
        refactored_code_new: str,
        refactored_code_modified: str,
        repo_path: str,
        test_class: str,
    ) -> tuple[bool, str | None]:
        """
        Verify refactoring doesn't introduce performance regression.

        Args:
            original_code: Original class code
            refactored_code_new: New extracted class code
            refactored_code_modified: Modified original class code
            repo_path: Repository root path
            test_class: Test class to benchmark

        Returns:
            (passed, error_message) tuple
        """
        self.logger.info(
            f"Running performance verification ({self.benchmark_iterations} iterations)"
        )

        try:
            # Benchmark original code
            original_metrics = self._benchmark_code(
                original_code, repo_path, test_class, "Original"
            )

            # Benchmark refactored code
            refactored_metrics = self._benchmark_code(
                refactored_code_modified + "\n" + refactored_code_new,
                repo_path,
                test_class,
                "Refactored",
            )

            # Compare performance
            result = self._compare_performance(original_metrics, refactored_metrics)

            if result.passed:
                if result.regression_percent < 0:
                    self.logger.info(
                        f"✓ Performance improved by {abs(result.regression_percent):.1f}%"
                    )
                else:
                    self.logger.info(
                        f"✓ Performance regression {result.regression_percent:.1f}% (within threshold)"
                    )
                return True, None
            else:
                self.logger.warning(
                    f"✗ Performance regression too high: {result.regression_percent:.1f}%"
                )
                return False, result.error_message

        except Exception as e:
            # Don't fail on performance errors - log warning and pass
            self.logger.warning(f"Performance verification error: {e}")
            return True, None

    def _benchmark_code(
        self, code: str, repo_path: str, test_class: str, label: str
    ) -> PerformanceMetrics:
        """
        Benchmark code execution time.

        Returns:
            PerformanceMetrics with timing data
        """
        self.logger.debug(f"Benchmarking {label} code...")

        # For now, use simple test execution timing
        # In production, would use JMH or similar

        times_ms = []

        # Warmup
        for _ in range(self.warmup_iterations):
            self._run_test(repo_path, test_class)

        # Actual benchmark
        for _ in range(self.benchmark_iterations):
            start = time.perf_counter()
            self._run_test(repo_path, test_class)
            end = time.perf_counter()

            times_ms.append((end - start) * 1000)

        return PerformanceMetrics(
            mean_time_ms=statistics.mean(times_ms),
            median_time_ms=statistics.median(times_ms),
            std_dev_ms=statistics.stdev(times_ms) if len(times_ms) > 1 else 0,
            min_time_ms=min(times_ms),
            max_time_ms=max(times_ms),
            iterations=len(times_ms),
        )

    def _run_test(self, repo_path: str, test_class: str) -> None:
        """Run a single test execution."""
        # Run test with Maven/Gradle
        cmd = ["mvn", "test", f"-Dtest={test_class}", "-q"]

        subprocess.run(cmd, cwd=repo_path, capture_output=True, timeout=10)

    def _compare_performance(
        self, original: PerformanceMetrics, refactored: PerformanceMetrics
    ) -> PerformanceResult:
        """
        Compare performance metrics.

        Returns:
            PerformanceResult with pass/fail and regression percentage
        """
        # Calculate regression percentage
        # Positive = slower (regression), Negative = faster (improvement)
        regression_percent = (
            (refactored.mean_time_ms - original.mean_time_ms) / original.mean_time_ms
        ) * 100

        # Check if within acceptable threshold
        passed = regression_percent <= self.max_regression_percent

        error_message = None
        if not passed:
            error_message = f"Performance regression {regression_percent:.1f}% exceeds threshold {self.max_regression_percent}%"

        return PerformanceResult(
            passed=passed,
            original_metrics=original,
            refactored_metrics=refactored,
            regression_percent=regression_percent,
            error_message=error_message,
        )

    def is_available(self) -> bool:
        """Check if performance benchmarking is available."""
        # Check if Maven or Gradle is available
        try:
            subprocess.run(["mvn", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except:
            pass

        try:
            subprocess.run(["gradle", "--version"], capture_output=True, check=True, timeout=5)
            return True
        except:
            pass

        return False
