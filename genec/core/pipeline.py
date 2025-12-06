"""Main GenEC pipeline orchestration."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from genec.core.cluster_detector import Cluster, ClusterDetector
from genec.core.dependency_analyzer import ClassDependencies
from genec.core.evolutionary_miner import EvolutionaryMiner
from genec.core.graph_builder import GraphBuilder
from genec.core.hybrid_dependency_analyzer import HybridDependencyAnalyzer
from genec.core.jdt_code_generator import JDTCodeGenerator
from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
from genec.core.pipeline_runner import PipelineRunner
from genec.core.refactoring_applicator import RefactoringApplication, RefactoringApplicator
from genec.core.stages.analysis_stage import AnalysisStage

# New Pipeline Architecture
from genec.core.stages.base_stage import PipelineContext
from genec.core.stages.clustering_stage import ClusteringStage
from genec.core.stages.graph_processing_stage import GraphProcessingStage
from genec.core.stages.naming_stage import NamingStage
from genec.core.stages.refactoring_stage import RefactoringStage
from genec.core.verification_engine import VerificationEngine, VerificationResult
from genec.metrics.cohesion_calculator import CohesionCalculator
from genec.metrics.coupling_calculator import CouplingCalculator
from genec.structural import StructuralTransformer, StructuralTransformResult
from genec.structural.compile_validator import StructuralCompileValidator
from genec.utils.dependency_manager import DependencyManager
from genec.utils.logging_utils import get_logger, setup_logger

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """Result of running the GenEC pipeline."""

    class_name: str
    suggestions: list[RefactoringSuggestion] = field(default_factory=list)
    verified_suggestions: list[RefactoringSuggestion] = field(default_factory=list)
    all_clusters: list[Cluster] = field(default_factory=list)
    filtered_clusters: list[Cluster] = field(default_factory=list)
    ranked_clusters: list[Cluster] = field(default_factory=list)
    verification_results: list[VerificationResult] = field(default_factory=list)
    applied_refactorings: list[RefactoringApplication] = field(default_factory=list)
    original_metrics: dict[str, float] = field(default_factory=dict)
    graph_metrics: dict[str, float] = field(default_factory=dict)
    graph_data: dict = field(default_factory=dict)
    execution_time: float = 0.0
    structural_actions: list[str] = field(default_factory=list)


class GenECPipeline:
    """Main GenEC pipeline for Extract Class refactoring."""

    def __init__(self, config_file: str = "config/config.yaml", config_overrides: dict = None):
        """
        Initialize GenEC pipeline.

        Args:
            config_file: Path to configuration file
            config_overrides: Dictionary of configuration overrides
        """
        self.logger = get_logger(self.__class__.__name__)
        self.logger.info("Initializing GenEC pipeline")

        # Load configuration
        self.config = self._load_config(config_file)

        # Apply overrides
        if config_overrides:
            self._apply_overrides(self.config, config_overrides)

        # Setup logging (re-setup with config if available)
        log_config = self.config.get("logging", {})
        self.logger = setup_logger(
            "GenEC", level=log_config.get("level", "INFO"), log_file=log_config.get("file")
        )

        self.logger.info("Initializing GenEC pipeline")

        # Ensure dependencies
        project_root = Path(__file__).parent.parent.parent
        self.dependency_manager = DependencyManager(project_root)

        # Check if auto-build is disabled via config
        auto_build = self.config.get("auto_build_dependencies", True)
        self.dependency_manager.ensure_dependencies(auto_build=auto_build)

        # Validate Java version (JDT requires Java 11+)
        self._validate_java_version()

        # Initialize components
        self._initialize_components()

    def _apply_overrides(self, config: dict, overrides: dict):
        """Recursively apply configuration overrides."""
        for key, value in overrides.items():
            if isinstance(value, dict) and key in config and isinstance(config[key], dict):
                self._apply_overrides(config[key], value)
            else:
                config[key] = value

    def _validate_java_version(self, min_version: int = 11):
        """
        Validate that Java is available and meets minimum version requirement.

        Args:
            min_version: Minimum required Java version (default: 11 for JDT)
        """
        import re
        import subprocess

        try:
            result = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, timeout=10
            )
            # Java version is printed to stderr
            version_output = result.stderr or result.stdout

            # Parse version from output like: openjdk version "11.0.12" or java version "1.8.0_301"
            version_match = re.search(r'version "(\d+)(?:\.(\d+))?', version_output)
            if version_match:
                major_version = int(version_match.group(1))
                # Handle old 1.x versioning (1.8 = Java 8)
                if major_version == 1 and version_match.group(2):
                    major_version = int(version_match.group(2))

                if major_version < min_version:
                    self.logger.warning(
                        f"Java {major_version} detected, but Java {min_version}+ is recommended. "
                        f"JDT code generation may not work correctly. "
                        f"Please upgrade Java or set JAVA_HOME to a newer version."
                    )
                else:
                    self.logger.debug(f"Java {major_version} detected (>= {min_version} required)")
            else:
                self.logger.warning(
                    f"Could not parse Java version from: {version_output[:100]}. "
                    f"Please ensure Java {min_version}+ is installed."
                )

        except FileNotFoundError:
            self.logger.warning(
                "Java not found in PATH. JDT code generation will be disabled. "
                "Please install Java 11+ or set JAVA_HOME."
            )
        except subprocess.TimeoutExpired:
            self.logger.warning("Java version check timed out.")
        except Exception as e:
            self.logger.debug(f"Java version check failed: {e}")

    def _load_config(self, config_file: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_file) as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Use default configuration with logger warning
            import logging

            logger = logging.getLogger("genec")
            logger.warning(
                f"Could not load config file '{config_file}': {e}. "
                f"Using default configuration (evolution window: 120 months, min cluster size: 3)."
            )
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Get default configuration."""
        return {
            "fusion": {"alpha": 0.5, "edge_threshold": 0.1},
            "evolution": {
                "window_months": 120,
                "min_commits": 2,
            },  # 10 years to capture full history
            "clustering": {
                "algorithm": "leiden",
                "min_cluster_size": 3,
                "max_cluster_size": 15,
                "min_cohesion": 0.5,
                "resolution": 1.0,
            },
            "chunking": {
                "enabled": True,
                "include_imports": True,
                "include_unused_fields_comment": True,
            },
            "llm": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "temperature": 0.3,
                "timeout": 120,
                "api_key": None,
            },
            "code_generation": {
                "engine": "eclipse_jdt",
                "jdt_wrapper_jar": "genec-jdt-wrapper/target/genec-jdt-wrapper-1.0.0-jar-with-dependencies.jar",
                "timeout": 60,
            },
            "verification": {
                "enable_syntactic": True,
                "enable_semantic": True,
                "enable_behavioral": True,
                "java_compiler": "javac",
                "maven_command": "mvn",
                "gradle_command": "gradle",
            },
            "structural_transforms": {
                "enabled": False,
                "require_confirmation": True,
                "compile_check": True,
                "max_methods": 40,
                "max_fields": 20,
                "output_dir": "data/outputs/structural_plans",
                "compile_command": ["mvn", "-q", "-DskipTests", "compile"],
                "compile_timeout_seconds": 300,
            },
            "refactoring_application": {
                "enabled": False,
                "auto_apply": False,
                "create_backups": True,
                "backup_dir": ".genec_backups",
                "dry_run": True,
            },
            "logging": {"level": "INFO"},
            "cache": {"enable": True, "directory": "data/outputs/cache"},
        }

    def _initialize_components(self):
        """Initialize all pipeline components."""
        # Dependency analyzer - Use hybrid (Spoon + JavaParser fallback)
        self.dependency_analyzer = HybridDependencyAnalyzer()

        # Evolutionary miner - Configure from config
        evolution_config = self.config.get("evolution", {})
        cache_dir = None
        if self.config.get("cache", {}).get("enable", True):
            cache_dir = self.config["cache"].get("directory", "data/outputs/cache")

        self.evolutionary_miner = EvolutionaryMiner(
            cache_dir=cache_dir,
            min_coupling_threshold=evolution_config.get("min_coupling_threshold", 0.3),
            max_changeset_size=evolution_config.get("max_changeset_size", 30),
            min_revisions=evolution_config.get("min_revisions", 5),
        )

        # Graph builder
        self.graph_builder = GraphBuilder()

        # Cluster detector
        cluster_config = self.config.get("clustering", {})
        self.cluster_detector = ClusterDetector(
            min_cluster_size=cluster_config.get("min_cluster_size", 3),
            max_cluster_size=cluster_config.get("max_cluster_size", 15),
            min_cohesion=cluster_config.get("min_cohesion", 0.5),
            resolution=cluster_config.get("resolution", 1.0),
            algorithm=cluster_config.get("algorithm", "leiden"),
            config=self.config,  # Pass full config for advanced features
        )

        # LLM interface
        llm_config = self.config.get("llm", {})
        chunking_config = self.config.get("chunking", {})
        self.llm_interface = LLMInterface(
            api_key=llm_config.get("api_key"),
            model=llm_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=llm_config.get("max_tokens", 4000),
            temperature=llm_config.get("temperature", 0.3),
            timeout=llm_config.get("timeout", 120),
            use_chunking=chunking_config.get("enabled", True),
        )

        # Code Generator - Eclipse JDT or String Manipulation
        codegen_config = self.config.get("code_generation", {})
        engine = codegen_config.get("engine", "eclipse_jdt")

        if engine == "eclipse_jdt":
            try:
                self.code_generator_class = JDTCodeGenerator

                # Resolve JAR path relative to project root if it's relative
                jar_path = codegen_config.get("jdt_wrapper_jar")
                project_root = Path(__file__).parent.parent.parent
                if not Path(jar_path).is_absolute():
                    self.jdt_wrapper_jar = str(project_root / jar_path)
                else:
                    self.jdt_wrapper_jar = jar_path

                self.jdt_timeout = codegen_config.get("timeout", 60)
                self.logger.info("Using Eclipse JDT for code generation")
            except Exception as e:
                self.logger.error(f"Eclipse JDT unavailable: {e}")
                raise
        else:
            raise ValueError(f"Unknown code generation engine: {engine}")

        # Store verification config for later initialization
        self.verify_config = self.config.get("verification", {})
        self.structural_config = self.config.get("structural_transforms", {})
        # Ensure defaults for structural config
        self.structural_config.setdefault("enabled", False)
        self.structural_config.setdefault("require_confirmation", True)
        self.structural_config.setdefault("compile_check", True)
        self.structural_config.setdefault("max_methods", 40)
        self.structural_config.setdefault("max_fields", 20)
        self.structural_config.setdefault("output_dir", "data/outputs/structural_plans")
        if self.structural_config.get("enabled"):
            self.logger.info(
                "Structural transformation stage enabled (max_methods=%s, max_fields=%s)",
                self.structural_config["max_methods"],
                self.structural_config["max_fields"],
            )
            output_dir = Path(
                self.structural_config.get("output_dir", "data/outputs/structural_plans")
            )
            self.structural_transformer = StructuralTransformer(output_dir)
        else:
            self.logger.info("Structural transformation stage disabled")
            self.structural_transformer = None
        self.verification_engine = None  # Will be initialized with repo_path in run_full_pipeline

        # Refactoring applicator
        self.refactoring_config = self.config.get("refactoring_application", {})
        self.refactoring_config.setdefault("enabled", False)
        self.refactoring_config.setdefault("auto_apply", False)
        self.refactoring_config.setdefault("create_backups", True)
        self.refactoring_config.setdefault("backup_dir", ".genec_backups")
        self.refactoring_config.setdefault("dry_run", True)

        if self.refactoring_config.get("enabled"):
            self.refactoring_applicator = RefactoringApplicator(
                create_backups=self.refactoring_config.get("create_backups", True),
                backup_dir=self.refactoring_config.get("backup_dir", ".genec_backups"),
            )
            mode = "DRY RUN" if self.refactoring_config.get("dry_run") else "LIVE"
            self.logger.info(f"Refactoring application enabled [{mode}]")
        else:
            self.refactoring_applicator = None
            self.logger.info("Refactoring application disabled")

        # Metrics calculators
        self.cohesion_calculator = CohesionCalculator()
        self.coupling_calculator = CouplingCalculator()

    def _emit_progress(self, stage: int, total: int, message: str, details: dict = None):
        """
        Emit structured JSON progress event to stderr for VS Code extension.

        Args:
            stage: Current stage number (0-indexed)
            total: Total number of stages
            message: Human-readable progress message
            details: Optional additional data (cluster count, method names, etc.)
        """
        import json
        import sys

        progress_event = {
            "type": "progress",
            "stage": stage,
            "total": total,
            "percent": int((stage / total) * 100) if total > 0 else 0,
            "message": message,
        }
        if details:
            progress_event["details"] = details

        # Write to stderr as single line JSON (extension can parse this)
        print(json.dumps(progress_event), file=sys.stderr, flush=True)

        # Also emit via WebSocket if server is running
        try:
            from genec.utils.progress_server import emit_progress as ws_emit

            ws_emit(stage, total, message, details)
        except Exception as e:
            self.logger.debug(f"WebSocket emit failed: {e}")

    def run_full_pipeline(
        self, class_file: str, repo_path: str, max_suggestions: int = None
    ) -> PipelineResult:
        """
        Run the complete GenEC pipeline.

        Args:
            class_file: Path to Java class file
            repo_path: Path to Git repository
            max_suggestions: Maximum number of suggestions to generate (None = all valid clusters)

        Returns:
            PipelineResult with all outputs
        """
        import time

        start_time = time.time()

        self.logger.info("=" * 80)
        self.logger.info(f"Running GenEC pipeline on {class_file}")
        self.logger.info("=" * 80)

        # Emit structured progress for VS Code extension (goes to stderr)
        self._emit_progress(stage=0, total=6, message="Initializing pipeline")

        # Initialize verification engine with repo_path
        if self.verification_engine is None:
            self.verification_engine = VerificationEngine(
                enable_syntactic=self.verify_config.get("enable_syntactic", True),
                enable_semantic=self.verify_config.get("enable_semantic", True),
                enable_behavioral=self.verify_config.get("enable_behavioral", False),
                enable_coverage=self.verify_config.get("enable_coverage", False),  # NEW
                java_compiler=self.verify_config.get("java_compiler", "javac"),
                maven_command=self.verify_config.get("maven_command", "mvn"),
                gradle_command=self.verify_config.get("gradle_command", "gradle"),
                repo_path=repo_path,
            )

        result = PipelineResult(class_name=Path(class_file).stem)

        try:
            # Update config with max_suggestions if provided
            if max_suggestions is not None:
                self.config["max_suggestions"] = max_suggestions

            # Create context
            context = PipelineContext(
                config=self.config, repo_path=repo_path, class_file=class_file
            )

            # Initialize stages
            stages = [
                AnalysisStage(
                    self.dependency_analyzer, self.evolutionary_miner, self.graph_builder
                ),
                GraphProcessingStage(self.graph_builder),
                ClusteringStage(self.cluster_detector),
                NamingStage(self.llm_interface),  # Changed self.suggester to self.llm_interface
                RefactoringStage(
                    self.refactoring_applicator, self.verification_engine
                ),  # Changed self.applicator to self.refactoring_applicator
            ]

            # Run pipeline
            runner = PipelineRunner(stages)
            results = runner.run(context)

            # Map results back to PipelineResult object
            result.class_dependencies = results.get("class_dependencies")
            result.fused_graph = results.get("fused_graph")
            result.centrality_metrics = results.get("centrality_metrics")
            result.graph_metrics = results.get("graph_metrics")
            result.graph_data = results.get("graph_data")
            result.all_clusters = results.get("all_clusters", [])
            result.filtered_clusters = results.get("filtered_clusters", [])
            result.ranked_clusters = results.get("ranked_clusters", [])
            result.suggestions = results.get("suggestions", [])
            result.verified_suggestions = results.get("verified_suggestions", [])

            result.execution_time = time.time() - start_time
            self.logger.info(f"Execution time: {result.execution_time:.2f} seconds")
            self.logger.info("=" * 80)

            self._emit_progress(stage=6, total=6, message="Pipeline completed")
            return result

        except Exception as e:
            self.logger.error(f"Pipeline error: {e}", exc_info=True)
            result.execution_time = time.time() - start_time
            return result

    def _calculate_class_metrics(self, class_deps: ClassDependencies) -> dict[str, float]:
        """Calculate quality metrics for a class."""
        metrics = {}

        # Cohesion metrics
        cohesion_metrics = self.cohesion_calculator.calculate_cohesion_metrics(class_deps)
        metrics.update(cohesion_metrics)

        # Coupling metrics
        coupling_metrics = self.coupling_calculator.calculate_coupling_metrics(class_deps)
        metrics.update(coupling_metrics)

        # Size metrics
        metrics["num_methods"] = len(class_deps.get_all_methods())
        metrics["num_fields"] = len(class_deps.fields)

        return metrics

    def _build_field_based_clusters(self, class_deps: ClassDependencies) -> list[Cluster]:
        """Construct fallback clusters based on field usage closure."""
        fields = [f.name for f in class_deps.fields]
        methods = class_deps.get_all_methods()

        field_usage: dict[str, set[str]] = {m.signature: set() for m in methods}

        for method in methods:
            body = method.body
            for field_name in fields:
                if re.search(rf"\b{re.escape(field_name)}\b", body):
                    field_usage[method.signature].add(field_name)

        field_to_methods: dict[str, set[str]] = {f: set() for f in fields}
        for signature, used_fields in field_usage.items():
            for field_name in used_fields:
                field_to_methods[field_name].add(signature)

        clusters: list[Cluster] = []
        cluster_id = 0

        for field_name, associated_methods in field_to_methods.items():
            if not associated_methods:
                continue

            member_methods = set(associated_methods)
            member_fields = {field_name}

            changed = True
            while changed:
                changed = False
                for method_sig in list(member_methods):
                    additional_fields = field_usage.get(method_sig, set()) - member_fields
                    if additional_fields:
                        member_fields.update(additional_fields)
                        changed = True
                for fld in list(member_fields):
                    additional_methods = field_to_methods.get(fld, set()) - member_methods
                    if additional_methods:
                        member_methods.update(additional_methods)
                        changed = True

            member_names = list(member_methods) + list(member_fields)

            if len(member_names) < self.cluster_detector.min_cluster_size:
                continue
            if len(member_names) > self.cluster_detector.max_cluster_size:
                continue

            member_types = {}
            for name in member_methods:
                member_types[name] = "method"
            for name in member_fields:
                member_types[name] = "field"

            cluster = Cluster(
                id=cluster_id,
                member_names=member_names,
                member_types=member_types,
                modularity=0.0,
                internal_cohesion=0.0,
                external_coupling=0.0,
            )
            clusters.append(cluster)
            cluster_id += 1

        return clusters

    def _run_structural_stage(
        self,
        clusters: list[Cluster],
        class_deps: ClassDependencies,
        repo_path: str,
        class_file: str,
    ) -> list[StructuralTransformResult]:
        """Generate structural transformation plans for rejected clusters."""
        if not self.structural_transformer:
            return []

        candidates = [cluster for cluster in clusters if getattr(cluster, "rejection_issues", None)]

        if not candidates:
            self.logger.info("Structural stage enabled but no rejected clusters captured.")
            return []

        self.logger.info(
            "Running structural transformation stage for %s rejected cluster(s)", len(candidates)
        )

        structural_results: list[StructuralTransformResult] = []
        for cluster in candidates:
            try:
                result = self.structural_transformer.attempt_transform(
                    cluster, class_deps, self.structural_config, repo_path, class_file
                )
                if result.actions:
                    structural_results.append(result)
            except Exception as exc:  # pragma: no cover - defensive
                self.logger.error(
                    "Structural transformation failed for cluster %s: %s", cluster.id, exc
                )

        return structural_results

    def _summarize_structural_result(self, result: StructuralTransformResult) -> str:
        """Convert structural result into concise summary text."""
        plan_paths = [
            action.artifacts.get("plan_path") for action in result.actions if action.artifacts
        ]
        plan_paths = [p for p in plan_paths if p]
        plan_info = (
            plan_paths[0] if plan_paths else (str(result.plan_path) if result.plan_path else "n/a")
        )
        notes = result.notes or ""
        return f"Cluster {result.cluster_id}: plan → {plan_info}. {notes}".strip()

    def _run_structural_compile_check(self, repo_path: str) -> str | None:
        """Run compile check after structural planning."""
        command = self.structural_config.get("compile_command")
        timeout = self.structural_config.get("compile_timeout_seconds", 300)

        if not command:
            self.logger.info("Structural compile check skipped (no command configured).")
            return None

        validator = StructuralCompileValidator(command, timeout_seconds=timeout)
        compile_result = validator.run(repo_path)

        if compile_result.success:
            self.logger.info("Structural compile check passed.")
        else:
            self.logger.error("Structural compile check failed.")

        return f"Structural compile check: {compile_result.summary()}"

    def check_prerequisites(self) -> dict[str, bool]:
        """
        Check that all required tools are available.

        Returns:
            Dictionary of tool names to availability status
        """
        self.logger.info("Checking prerequisites...")

        # Initialize verification engine temporarily if not yet initialized
        if self.verification_engine is None:
            temp_engine = VerificationEngine(
                enable_syntactic=self.verify_config.get("enable_syntactic", True),
                enable_semantic=self.verify_config.get("enable_semantic", True),
                enable_behavioral=self.verify_config.get("enable_behavioral", False),
                java_compiler=self.verify_config.get("java_compiler", "javac"),
                maven_command=self.verify_config.get("maven_command", "mvn"),
                gradle_command=self.verify_config.get("gradle_command", "gradle"),
            )
            status = temp_engine.check_prerequisites()
        else:
            status = self.verification_engine.check_prerequisites()

        for tool, available in status.items():
            if available:
                self.logger.info(f"{tool} is available")
            else:
                self.logger.warning(f"{tool} is NOT available")

        return status
