"""
Structural transformation scaffolding for complex extractions.

This module generates façade/accessor plans for clusters that require
deeper architectural changes (e.g., inner class adapters, dependency
injection) before an Extract Class refactoring can succeed.

The current implementation focuses on analysing blocking issues and
producing actionable plans (stored under data/outputs/structural_plans/)
without yet mutating the original source. Future iterations can build on
these plans to perform the actual rewrites automatically.
"""

from __future__ import annotations

import datetime
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from genec.core.cluster_detector import Cluster
from genec.core.dependency_analyzer import ClassDependencies
from genec.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class StructuralAction:
    """Describes a suggested structural change."""

    description: str
    details: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)  # filename -> content


@dataclass
class StructuralTransformResult:
    """Result of attempting a structural transformation."""

    cluster_id: int
    applied: bool
    actions: list[StructuralAction] = field(default_factory=list)
    notes: str | None = None
    plan_path: Path | None = None


class StructuralTransformer:
    """
    Generates façade/accessor scaffolding plans for problematic clusters.

    The transformer currently produces guidance artefacts (markdown plan files)
    rather than mutating the target project. This keeps the pipeline safe while
    providing developers with a concrete blueprint for manual or semi-automated
    follow-up.
    """

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.logger = get_logger(self.__class__.__name__)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def attempt_transform(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies,
        structural_config: dict,
        repo_path: str,
        class_file: str,
    ) -> StructuralTransformResult:
        """
        Attempt to generate a structural transformation plan for the cluster.

        Returns:
            StructuralTransformResult (applied will be False until automatic
            rewrites are implemented).
        """
        max_methods = structural_config.get("max_methods", 40)
        max_fields = structural_config.get("max_fields", 20)
        method_count = len(cluster.get_methods())
        field_count = len(cluster.get_fields())

        if method_count > max_methods or field_count > max_fields:
            note = (
                f"Cluster too large for automated structural plan "
                f"({method_count} methods, {field_count} fields)"
            )
            self.logger.info("Skipping structural plan for cluster %s: %s", cluster.id, note)
            return StructuralTransformResult(
                cluster_id=cluster.id,
                applied=False,
                notes=note,
            )

        issues = getattr(cluster, "rejection_issues", []) or []
        if not issues:
            return StructuralTransformResult(
                cluster_id=cluster.id,
                applied=False,
                notes="No rejection issues captured; skipping structural plan.",
            )

        action = self._build_plan(cluster, class_deps, issues, repo_path, class_file)

        return StructuralTransformResult(
            cluster_id=cluster.id,
            applied=False,
            actions=[action],
            plan_path=Path(action.artifacts.get("plan_path")) if action.artifacts else None,
            notes="Structural scaffolding plan generated; manual review required.",
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _build_plan(
        self,
        cluster: Cluster,
        class_deps: ClassDependencies,
        issues: list,
        repo_path: str,
        class_file: str,
    ) -> StructuralAction:
        """Create a markdown plan summarising required structural changes."""
        class_name = class_deps.class_name
        timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        cluster_dir = self.output_dir / class_name
        cluster_dir.mkdir(parents=True, exist_ok=True)

        plan_path = cluster_dir / f"cluster_{cluster.id:02d}_structural_plan.md"

        inner_classes = sorted(
            {
                issue.description.split("'")[1]
                for issue in issues
                if "inner class" in issue.description
            }
        )
        abstract_calls = sorted(
            {
                issue.description.split("'")[1]
                for issue in issues
                if "abstract method" in issue.description
            }
        )

        methods = "\n".join(f"- {m}" for m in cluster.get_methods())
        fields = "\n".join(f"- {f}" for f in cluster.get_fields()) or "- (none)"

        plan_body = textwrap.dedent(
            f"""
            # Structural Refactoring Plan for {class_name} – Cluster {cluster.id}

            Generated: {timestamp}
            Repository: {repo_path}
            Source File: {class_file}

            ## Extracted Members
            Methods:
            {methods or '- (none)'}

            Fields:
            {fields}

            ## Detected Blocking Issues
            """
        ).strip()

        issue_lines = "\n".join(f"- {issue.description}" for issue in issues)

        scaffolding_section = self._render_scaffolding_section(
            class_name, inner_classes, abstract_calls
        )

        plan_content = "\n\n".join(
            part
            for part in [
                plan_body,
                issue_lines,
                scaffolding_section,
            ]
            if part
        )

        plan_path.write_text(plan_content, encoding="utf-8")

        self.logger.info("Wrote structural plan for cluster %s → %s", cluster.id, plan_path)

        return StructuralAction(
            description="Generated structural transformation plan",
            details=(
                "Plan outlines façade/accessor scaffolding needed before extraction. "
                "Manual confirmation required."
            ),
            artifacts={"plan_path": str(plan_path)},
        )

    def _render_scaffolding_section(
        self,
        class_name: str,
        inner_classes: list[str],
        abstract_calls: list[str],
    ) -> str:
        """Render guidance text for façade/accessor scaffolding."""
        inner_section = (
            "### Inner Class Abstractions\n"
            + "\n".join(
                f"- Extract interface `{name}View` exposing required members."
                for name in inner_classes
            )
            if inner_classes
            else "### Inner Class Abstractions\n- None detected."
        )

        abstract_section = (
            "### Abstract Method Adaptations\n"
            + "\n".join(
                f"- Provide Strategy/Callback override for `{sig}`." for sig in abstract_calls
            )
            if abstract_calls
            else "### Abstract Method Adaptations\n- None detected."
        )

        skeleton = textwrap.dedent(
            f"""
            ## Suggested Scaffolding

            {inner_section}

            {abstract_section}

            ### Proposed Accessor Interface
            ```java
            interface {class_name}StateAccessor {{
                Object getCurrentValue();
                boolean casValue(Object expect, Object update);
                boolean isDone();
                boolean wasInterrupted();
                // TODO: add remaining helpers surfaced by validation
            }}
            ```

            ### Suggested Helper Skeleton
            ```java
            final class {class_name}Operations {{
                private final {class_name}StateAccessor accessor;

                {class_name}Operations({class_name}StateAccessor accessor) {{
                    this.accessor = accessor;
                }}

                // TODO: migrate extracted methods here.
            }}
            ```
            """
        ).strip()

        return skeleton
