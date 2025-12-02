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
from genec.core.jdt_code_generator import CodeGenerationError, JDTCodeGenerator
from genec.core.llm_interface import LLMInterface, RefactoringSuggestion
from genec.core.refactoring_applicator import RefactoringApplication, RefactoringApplicator
from genec.core.verification_engine import VerificationEngine, VerificationResult
from genec.metrics.cohesion_calculator import CohesionCalculator
from genec.metrics.coupling_calculator import CouplingCalculator
from genec.structural import StructuralTransformer, StructuralTransformResult
from genec.structural.compile_validator import StructuralCompileValidator
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
    execution_time: float = 0.0
    structural_actions: list[str] = field(default_factory=list)


class GenECPipeline:
    """Main GenEC pipeline for Extract Class refactoring."""

    def __init__(self, config_file: str = "config/config.yaml"):
        """
        Initialize GenEC pipeline.

        Args:
            config_file: Path to configuration file
        """
        # Load configuration
        self.config = self._load_config(config_file)

        # Setup logging
        log_config = self.config.get("logging", {})
        self.logger = setup_logger(
            "GenEC", level=log_config.get("level", "INFO"), log_file=log_config.get("file")
        )

        self.logger.info("Initializing GenEC pipeline")

        # Initialize components
        self._initialize_components()

    def _load_config(self, config_file: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_file) as f:
                return yaml.safe_load(f)
        except Exception as e:
            # Use default configuration
            print(f"Warning: Could not load config file {config_file}: {e}")
            print("Using default configuration")
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Get default configuration."""
        return {
            "fusion": {"alpha": 0.5, "edge_threshold": 0.1},
            "evolution": {"window_months": 12, "min_commits": 2},
            "clustering": {
                "algorithm": "louvain",
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
                self.jdt_wrapper_jar = codegen_config.get("jdt_wrapper_jar")
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

        # Initialize verification engine with repo_path
        if self.verification_engine is None:
            self.verification_engine = VerificationEngine(
                enable_syntactic=self.verify_config.get("enable_syntactic", True),
                enable_semantic=self.verify_config.get("enable_semantic", True),
                enable_behavioral=self.verify_config.get("enable_behavioral", False),
                java_compiler=self.verify_config.get("java_compiler", "javac"),
                maven_command=self.verify_config.get("maven_command", "mvn"),
                gradle_command=self.verify_config.get("gradle_command", "gradle"),
                repo_path=repo_path,
            )

        result = PipelineResult(class_name=Path(class_file).stem)

        try:
            # Stage 1: Analyze static dependencies
            self.logger.info("\n[Stage 1/6] Analyzing static dependencies...")
            class_deps = self.dependency_analyzer.analyze_class(class_file)

            if not class_deps:
                self.logger.error("Failed to analyze class dependencies")
                return result

            result.class_name = class_deps.class_name

            # Calculate original metrics
            result.original_metrics = self._calculate_class_metrics(class_deps)
            self.logger.info(f"Original metrics: {result.original_metrics}")

            # Read original code
            with open(class_file, encoding="utf-8") as f:
                original_code = f.read()

            # Stage 2: Mine evolutionary coupling
            self.logger.info("\n[Stage 2/6] Mining evolutionary coupling from Git history...")
            evo_config = self.config.get("evolution", {})

            # Convert absolute path to relative path from repo root
            class_file_path = Path(class_file).resolve()
            repo_path_obj = Path(repo_path).resolve()

            try:
                relative_path = class_file_path.relative_to(repo_path_obj)
                relative_path_str = str(relative_path)
            except ValueError:
                self.logger.warning(f"Class file {class_file} is not in repo {repo_path}")
                relative_path_str = class_file

            evo_data = self.evolutionary_miner.mine_method_cochanges(
                relative_path_str,
                repo_path,
                window_months=evo_config.get("window_months", 12),
                min_commits=evo_config.get("min_commits", 2),
            )

            # Stage 3: Build and fuse graphs
            self.logger.info("\n[Stage 3/6] Building and fusing dependency graphs...")

            G_static = self.graph_builder.build_static_graph(class_deps)

            # Build method name to signature mapping for evolutionary graph
            method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
            G_evo = self.graph_builder.build_evolutionary_graph(evo_data, method_map)

            fusion_config = self.config.get("fusion", {})
            G_fused = self.graph_builder.fuse_graphs(
                G_static,
                G_evo,
                alpha=fusion_config.get("alpha", 0.5),
                edge_threshold=fusion_config.get("edge_threshold", 0.1),
            )

            # Calculate graph metrics
            result.graph_metrics = self.graph_builder.get_graph_metrics(G_fused)
            self.logger.info(f"Graph metrics: {result.graph_metrics}")

            # Stage 4: Detect, filter, and rank clusters
            self.logger.info("\n[Stage 4/6] Detecting and ranking clusters...")

            all_clusters = self.cluster_detector.detect_clusters(G_fused)
            result.all_clusters = all_clusters

            # Pass class_deps to enable extraction validation
            filtered_clusters = self.cluster_detector.filter_clusters(all_clusters, class_deps)
            result.filtered_clusters = filtered_clusters

            ranked_clusters = self.cluster_detector.rank_clusters(filtered_clusters)
            result.ranked_clusters = ranked_clusters

            self.logger.info(
                f"Clusters: {len(all_clusters)} detected, "
                f"{len(filtered_clusters)} filtered, "
                f"{len(ranked_clusters)} ranked"
            )

            if not ranked_clusters:
                self.logger.warning("No viable clusters found")

                if self.structural_config.get("enabled"):
                    structural_results = self._run_structural_stage(
                        all_clusters,
                        class_deps,
                        repo_path,
                        class_file,
                    )
                    result.structural_actions = [
                        self._summarize_structural_result(r) for r in structural_results
                    ]
                    if structural_results and self.structural_config.get("compile_check", True):
                        compile_summary = self._run_structural_compile_check(repo_path)
                        if compile_summary:
                            result.structural_actions.append(compile_summary)
                    if structural_results:
                        self.logger.info(
                            "Generated %s structural transformation plan(s)",
                            len(structural_results),
                        )
                return result

            # Stage 5: Generate suggestions (LLM for naming + deterministic code)
            num_to_process = "all" if max_suggestions is None else f"top {max_suggestions}"
            self.logger.info(
                f"\n[Stage 5/6] Generating refactoring suggestions ({num_to_process})..."
            )

            suggestions: list[RefactoringSuggestion] = []

            if not self.llm_interface.is_available():
                self.logger.warning("LLM interface unavailable; skipping suggestion generation.")
            else:
                clusters_to_process = (
                    ranked_clusters
                    if max_suggestions is None
                    else ranked_clusters[:max_suggestions]
                )
                for cluster in clusters_to_process:
                    suggestion = self.llm_interface.generate_refactoring_suggestion(
                        cluster, original_code, class_deps, evo_data=evo_data
                    )

                    if not suggestion:
                        continue

                    # Use JDT code generator
                    generator = JDTCodeGenerator(
                        jdt_wrapper_jar=self.jdt_wrapper_jar, timeout=self.jdt_timeout
                    )
                    try:
                        generated = generator.generate(
                            cluster=cluster,
                            new_class_name=suggestion.proposed_class_name,
                            class_file=class_file,
                            repo_path=repo_path,
                            class_deps=class_deps,
                        )
                    except CodeGenerationError as e:
                        self.logger.warning(
                            f"Skipping cluster {cluster.id} ({suggestion.proposed_class_name}): {e}"
                        )
                        continue

                    suggestion.new_class_code = generated.new_class_code
                    suggestion.modified_original_code = generated.modified_original_code
                    suggestions.append(suggestion)

            result.suggestions = suggestions

            self.logger.info(f"Generated {len(suggestions)} suggestions")

            # Stage 6: Verify suggestions
            if not suggestions:
                self.logger.warning(
                    "No suggestions from ranked clusters; attempting field-based fallback."
                )

                fallback_clusters = self._build_field_based_clusters(class_deps)
                seen = set()
                for cluster in fallback_clusters:
                    if max_suggestions is not None and len(suggestions) >= max_suggestions:
                        break
                    key = tuple(sorted(cluster.member_names))
                    if key in seen:
                        continue
                    seen.add(key)

                    suggestion = self.llm_interface.generate_refactoring_suggestion(
                        cluster, original_code, class_deps, evo_data=evo_data
                    )

                    if not suggestion:
                        continue

                    generator = JDTCodeGenerator(
                        jdt_wrapper_jar=self.jdt_wrapper_jar, timeout=self.jdt_timeout
                    )
                    try:
                        generated = generator.generate(
                            cluster=cluster,
                            new_class_name=suggestion.proposed_class_name,
                            class_file=class_file,
                            repo_path=repo_path,
                            class_deps=class_deps,
                        )
                    except CodeGenerationError as e:
                        self.logger.warning(
                            f"Skipping fallback cluster {cluster.id} ({suggestion.proposed_class_name}): {e}"
                        )
                        continue

                    suggestion.new_class_code = generated.new_class_code
                    suggestion.modified_original_code = generated.modified_original_code
                    suggestions.append(suggestion)

                result.suggestions = suggestions

            if not suggestions:
                self.logger.warning("No suggestions to verify; skipping verification stage.")
            else:
                self.logger.info("\n[Stage 6/6] Verifying refactoring suggestions...")

                # Parallel Verification
                import concurrent.futures

                # Determine max workers (default to 4 or config)
                max_workers = self.verify_config.get("max_workers", 4)
                self.logger.info(
                    f"Verifying {len(suggestions)} suggestions in parallel (max_workers={max_workers})"
                )

                def verify_single_suggestion(suggestion):
                    self.logger.info(f"Verifying suggestion: {suggestion.proposed_class_name}")
                    return self.verification_engine.verify_refactoring(
                        suggestion, original_code, class_file, repo_path, class_deps
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_suggestion = {
                        executor.submit(verify_single_suggestion, s): s for s in suggestions
                    }

                    for future in concurrent.futures.as_completed(future_to_suggestion):
                        suggestion = future_to_suggestion[future]
                        try:
                            verification_result = future.result()
                            result.verification_results.append(verification_result)

                            if verification_result.status == "PASSED_ALL":
                                result.verified_suggestions.append(suggestion)
                                self.logger.info(
                                    f"Suggestion {suggestion.proposed_class_name} PASSED all verification layers"
                                )
                            else:
                                self.logger.warning(
                                    f"Suggestion {suggestion.proposed_class_name} FAILED: {verification_result.status} - "
                                    f"{verification_result.error_message}"
                                )
                        except Exception as exc:
                            self.logger.error(
                                f"Verification generated an exception for {suggestion.proposed_class_name}: {exc}"
                            )

            # Stage 7: Apply refactorings (if enabled)
            if self.refactoring_applicator and result.verified_suggestions:
                self.logger.info("\n[Stage 7/7] Applying verified refactorings...")

                dry_run = self.refactoring_config.get("dry_run", True)
                auto_apply = self.refactoring_config.get("auto_apply", False)

                if not auto_apply and not dry_run:
                    self.logger.warning(
                        "auto_apply=False: Refactorings will not be applied. "
                        "Set auto_apply=True to enable automatic application."
                    )
                else:
                    for i, suggestion in enumerate(result.verified_suggestions, 1):
                        self.logger.info(
                            f"Applying refactoring {i}/{len(result.verified_suggestions)}: "
                            f"{suggestion.proposed_class_name}"
                        )

                        application = self.refactoring_applicator.apply_refactoring(
                            suggestion=suggestion,
                            original_class_file=class_file,
                            repo_path=repo_path,
                            dry_run=dry_run,
                        )

                        result.applied_refactorings.append(application)

                        if application.success:
                            if dry_run:
                                self.logger.info(
                                    f"[DRY RUN] Would create: {application.new_class_path}"
                                )
                            else:
                                self.logger.info(
                                    f"Successfully applied refactoring: {application.new_class_path}"
                                )
                        else:
                            self.logger.error(
                                f"Failed to apply refactoring: {application.error_message}"
                            )

            # Calculate execution time
            result.execution_time = time.time() - start_time

            # Summary
            self.logger.info("\n" + "=" * 80)
            self.logger.info("PIPELINE SUMMARY")
            self.logger.info("=" * 80)
            self.logger.info(f"Class: {result.class_name}")
            self.logger.info(f"Clusters detected: {len(result.all_clusters)}")
            self.logger.info(f"Suggestions generated: {len(result.suggestions)}")
            self.logger.info(f"Verified suggestions: {len(result.verified_suggestions)}")
            if result.applied_refactorings:
                successful_applications = sum(
                    1 for app in result.applied_refactorings if app.success
                )
                self.logger.info(
                    f"Applied refactorings: {successful_applications}/{len(result.applied_refactorings)}"
                )
            self.logger.info(f"Execution time: {result.execution_time:.2f} seconds")
            self.logger.info("=" * 80)

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
            for field in fields:
                if re.search(rf"\b{re.escape(field)}\b", body):
                    field_usage[method.signature].add(field)

        field_to_methods: dict[str, set[str]] = {f: set() for f in fields}
        for signature, used_fields in field_usage.items():
            for field in used_fields:
                field_to_methods[field].add(signature)

        clusters: list[Cluster] = []
        cluster_id = 0

        for field, associated_methods in field_to_methods.items():
            if not associated_methods:
                continue

            member_methods = set(associated_methods)
            member_fields = {field}

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
