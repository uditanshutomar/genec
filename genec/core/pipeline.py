"""Main GenEC pipeline orchestration."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from genec.core.cluster_detector import (
    Cluster,
    ClusterDetector,
    QualityTier,
    calculate_quality_tier,
)
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
        import subprocess
        import re
        
        try:
            result = subprocess.run(
                ['java', '-version'],
                capture_output=True,
                text=True,
                timeout=10
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

            # Read original code with size warning
            with open(class_file, encoding="utf-8") as f:
                original_code = f.read()
            
            # Check file size and warn/refuse for large files
            line_count = original_code.count('\n')
            file_size_mb = len(original_code.encode('utf-8')) / (1024 * 1024)
            
            # Hard limit: refuse files over 100k lines to prevent OOM
            if line_count > 100000:
                self.logger.error(
                    f"File too large: {line_count} lines ({file_size_mb:.1f}MB). "
                    f"GenEC supports files up to 100,000 lines. "
                    f"Please split this file manually first."
                )
                return result
            elif line_count > 10000:
                self.logger.warning(
                    f"Large file detected: {line_count} lines ({file_size_mb:.1f}MB). "
                    f"Analysis may be slow and memory-intensive. "
                    f"Consider splitting very large classes manually first."
                )
            elif line_count > 5000:
                self.logger.info(f"Processing large file with {line_count} lines...")

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
                window_months=evo_config.get("window_months", 120),  # Default to 10 years
                min_commits=evo_config.get("min_commits", 2),
            )

            # Stage 3: Build and fuse graphs
            self.logger.info("\n[Stage 3/6] Building and fusing dependency graphs...")

            G_static = self.graph_builder.build_static_graph(class_deps)

            # Build method name to signature mapping for evolutionary graph
            method_map = {m.name: m.signature for m in class_deps.get_all_methods()}
            G_evo = self.graph_builder.build_evolutionary_graph(evo_data, method_map)

            fusion_config = self.config.get("fusion", {})

            # Get hotspot data for adaptive fusion
            hotspot_data = None
            adaptive_fusion = fusion_config.get("adaptive_fusion", False)
            if adaptive_fusion and evo_data.method_names:
                # Calculate hotspots from evolutionary data
                try:
                    hotspot_data = self.evolutionary_miner.get_method_hotspots(
                        evo_data, top_n=len(evo_data.method_names)
                    )
                    self.logger.info(
                        f"Using adaptive fusion with {len(hotspot_data)} hotspot scores"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to calculate hotspots for adaptive fusion: {e}. "
                        f"Falling back to regular fusion."
                    )
                    hotspot_data = None

            G_fused = self.graph_builder.fuse_graphs(
                G_static,
                G_evo,
                alpha=fusion_config.get("alpha", 0.5),
                edge_threshold=fusion_config.get("edge_threshold", 0.1),
                hotspot_data=hotspot_data,
                adaptive_fusion=adaptive_fusion,
            )

            # Calculate centrality metrics
            centrality_config = fusion_config.get("centrality", {})
            if centrality_config.get("enabled", True):
                top_n = centrality_config.get("top_n", 10)
                centrality_metrics = self.graph_builder.calculate_centrality_metrics(
                    G_fused, top_n=top_n
                )

                # Add to graph nodes if requested
                if centrality_config.get("add_to_graph", True):
                    G_fused = self.graph_builder.add_centrality_to_graph(
                        G_fused, centrality_metrics
                    )

                # Store centrality in result
                result.centrality_metrics = centrality_metrics
                self.logger.info(f"Calculated {len(centrality_metrics)} centrality metrics")

            # Calculate graph metrics
            result.graph_metrics = self.graph_builder.get_graph_metrics(G_fused)
            self.logger.info(f"Graph metrics: {result.graph_metrics}")

            # Generate graph data for JSON output
            from networkx.readwrite import json_graph

            result.graph_data = json_graph.node_link_data(G_fused, edges="links")

            # Export graph if requested
            export_config = fusion_config.get("export", {})
            if export_config.get("enabled", False):
                output_dir = Path(export_config.get("output_dir", "output/graphs"))
                output_dir.mkdir(parents=True, exist_ok=True)

                class_name = class_deps.class_name
                formats = export_config.get("formats", ["graphml", "json"])

                for fmt in formats:
                    try:
                        output_file = output_dir / f"{class_name}_fused.{fmt}"
                        self.graph_builder.export_graph(G_fused, str(output_file), format=fmt)
                        self.logger.info(f"Exported graph to {output_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to export graph as {fmt}: {e}")

                # Export centrality metrics if calculated
                if hasattr(result, "centrality_metrics"):
                    centrality_file = output_dir / f"{class_name}_centrality.json"
                    try:
                        self.graph_builder.export_centrality_metrics(
                            result.centrality_metrics, str(centrality_file), format="json"
                        )
                        self.logger.info(f"Exported centrality metrics to {centrality_file}")
                    except Exception as e:
                        self.logger.warning(f"Failed to export centrality metrics: {e}")

            # Stage 4: Detect, filter, and rank clusters
            self.logger.info("\n[Stage 4/6] Detecting and ranking clusters...")

            all_clusters = self.cluster_detector.detect_clusters(G_fused, class_deps)
            result.all_clusters = all_clusters

            # Calculate quality tiers for all clusters
            for cluster in all_clusters:
                calculate_quality_tier(cluster, evo_data)

            # Separate clusters by quality tier
            should_clusters = [c for c in all_clusters if c.quality_tier == QualityTier.SHOULD]
            could_clusters = [c for c in all_clusters if c.quality_tier == QualityTier.COULD]
            potential_clusters = [
                c for c in all_clusters if c.quality_tier == QualityTier.POTENTIAL
            ]

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
            self.logger.info(
                f"Quality tiers: SHOULD={len(should_clusters)}, "
                f"COULD={len(could_clusters)}, "
                f"POTENTIAL={len(potential_clusters)}"
            )

            if not ranked_clusters:
                self.logger.warning("No viable clusters found after filtering")
                self.logger.info(
                    "Will still generate suggestions for all quality tiers (SHOULD/COULD/POTENTIAL)"
                )

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
                # Don't return early - continue to tier-based suggestion generation

            # Stage 5: Generate suggestions (LLM for naming + deterministic code)
            num_to_process = "all" if max_suggestions is None else f"top {max_suggestions}"
            self.logger.info(
                f"\n[Stage 5/6] Generating refactoring suggestions ({num_to_process})..."
            )

            suggestions: list[RefactoringSuggestion] = []

            if not self.llm_interface.is_available():
                self.logger.warning("LLM interface unavailable; skipping suggestion generation.")
            else:
                # Generate suggestions for all quality tiers
                # Process SHOULD tier (high quality - always generate)
                all_tier_clusters = should_clusters + could_clusters + potential_clusters

                # Use parallel batch generation
                # This handles both LLM generation and JDT code generation (via hybrid mode) in parallel
                # Generate ALL suggestions across all tiers (ignore max_suggestions for tiered mode)
                suggestions = self.llm_interface.generate_batch_suggestions(
                    clusters=all_tier_clusters,
                    original_code=original_code,
                    class_deps=class_deps,
                    class_file=class_file,
                    repo_path=repo_path,
                    evo_data=evo_data,
                    max_suggestions=None,  # Generate all suggestions for all tiers
                    max_workers=4,  # Default to 4 workers
                )

                # Tag suggestions with quality tier metadata from their clusters
                for suggestion in suggestions:
                    if suggestion.cluster:
                        suggestion.quality_tier = (
                            suggestion.cluster.quality_tier.value
                            if suggestion.cluster.quality_tier
                            else None
                        )
                        suggestion.quality_score = suggestion.cluster.quality_score
                        suggestion.quality_reasons = suggestion.cluster.quality_reasons

            result.suggestions = suggestions

            # Separate suggestions by tier for reporting
            should_suggestions = [s for s in suggestions if s.quality_tier == "should"]
            could_suggestions = [s for s in suggestions if s.quality_tier == "could"]
            potential_suggestions = [s for s in suggestions if s.quality_tier == "potential"]

            self.logger.info(f"Generated {len(suggestions)} total suggestions")
            self.logger.info(
                f"  ✅ SHOULD: {len(should_suggestions)} (high quality, strong recommendation)"
            )
            self.logger.info(f"  ⚠️  COULD: {len(could_suggestions)} (medium quality, conditional)")
            self.logger.info(
                f"  💡 POTENTIAL: {len(potential_suggestions)} (low quality, informational)"
            )

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
                        cluster=cluster,
                        original_code=original_code,
                        class_deps=class_deps,
                        class_file=class_file,  # NEW: Enable hybrid mode
                        repo_path=repo_path,  # NEW: Enable hybrid mode
                        evo_data=evo_data,
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

                    # Skip heavy behavioral verification for non-SHOULD tiers
                    # Only SHOULD tier gets auto-applied, so others just need syntax check
                    if suggestion.quality_tier != "should":
                        self.logger.info(
                            f"Skipping heavy verification for {suggestion.quality_tier.upper()} tier: "
                            f"{suggestion.proposed_class_name} (syntax-only)"
                        )
                        # Create lightweight verification engine for non-SHOULD
                        from genec.core.verification_engine import (
                            VerificationEngine,
                        )

                        lightweight_engine = VerificationEngine(
                            enable_equivalence=False,
                            enable_syntactic=True,
                            enable_semantic=True,
                            enable_behavioral=False,  # Skip expensive behavioral tests
                            repo_path=repo_path,
                        )
                        return lightweight_engine.verify_refactoring(
                            suggestion, original_code, class_file, repo_path, class_deps
                        )

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

                # Initialize Preview Manager
                from genec.core.preview_manager import PreviewManager

                preview_manager = PreviewManager()

                # Generate previews
                original_files = {s.cluster_id: class_file for s in result.verified_suggestions}
                previews = preview_manager.preview_multiple(
                    result.verified_suggestions, original_files, repo_path
                )

                # Log preview summary
                summary = preview_manager.format_summary(previews)
                self.logger.info("\n" + summary)

                if dry_run:
                    # Detailed preview for dry run
                    for preview in previews:
                        self.logger.info("\n" + preview_manager.format_preview(preview))

                    # Add dummy applications for result tracking
                    for suggestion in result.verified_suggestions:
                        result.applied_refactorings.append(
                            RefactoringApplication(
                                success=True,
                                new_class_path=f"[DRY RUN] {suggestion.proposed_class_name}.java",
                                original_class_path=class_file,
                            )
                        )

                elif not auto_apply:
                    self.logger.warning(
                        "auto_apply=False: Refactorings will not be applied. "
                        "Set auto_apply=True to enable automatic application."
                    )
                else:
                    # Transactional Application
                    from genec.core.transactional_applicator import TransactionalApplicator

                    transactional_applicator = TransactionalApplicator(
                        applicator=self.refactoring_applicator,
                        enable_git=self.refactoring_applicator.enable_git,
                    )

                    # Auto-apply only SHOULD tier suggestions (high quality, strong evidence)
                    should_verified = [
                        s for s in result.verified_suggestions if s.quality_tier == "should"
                    ]

                    if should_verified:
                        self.logger.info(
                            f"Auto-applying {len(should_verified)} SHOULD-tier suggestions (high quality)"
                        )
                        success, applications = transactional_applicator.apply_all(
                            suggestions=should_verified,
                            original_files=original_files,
                            repo_path=repo_path,
                            check_conflicts=True,
                        )
                    else:
                        self.logger.info("No SHOULD-tier suggestions to auto-apply")
                        success = True
                        applications = []

                    # Log COULD and POTENTIAL suggestions for user review
                    could_verified = [
                        s for s in result.verified_suggestions if s.quality_tier == "could"
                    ]
                    potential_verified = [
                        s for s in result.verified_suggestions if s.quality_tier == "potential"
                    ]

                    if could_verified:
                        self.logger.info(
                            f"⚠️  {len(could_verified)} COULD-tier suggestions available for review (medium quality)"
                        )
                    if potential_verified:
                        self.logger.info(
                            f"💡 {len(potential_verified)} POTENTIAL-tier suggestions available for review (low quality)"
                        )

                    result.applied_refactorings = applications

                    if success:
                        self.logger.info("Successfully applied all refactorings transactionally")
                    else:
                        self.logger.error("Transactional application failed (rolled back)")

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
