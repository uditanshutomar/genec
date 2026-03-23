from genec.core.refactoring_applicator import RefactoringApplicator
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.core.verification_engine import VerificationEngine
from genec.utils.logging_utils import get_logger
from genec.utils.progress_server import emit_progress

logger = get_logger(__name__)


class RefactoringStage(PipelineStage):
    """Stage for applying and verifying refactorings."""

    def __init__(self, applicator: RefactoringApplicator, verification_engine: VerificationEngine):
        super().__init__("Refactoring")
        self.applicator = applicator
        self.verification_engine = verification_engine

    def run(self, context: PipelineContext) -> bool:
        app_config = context.config.get("refactoring_application", {})
        apply_enabled = app_config.get("enabled", False) and self.applicator is not None

        emit_progress(6, 6, "Verifying refactorings...")
        self.logger.info("\n[Stage 6/6] Verifying refactorings...")

        suggestions = context.get("suggestions", [])
        if not suggestions:
            self.logger.info("No suggestions to verify")
            return True

        auto_apply = app_config.get("auto_apply", False) if apply_enabled else False
        dry_run = app_config.get("dry_run", False) if apply_enabled else False
        should_apply = apply_enabled and not dry_run

        if apply_enabled:
            mode = "DRY RUN" if dry_run else "LIVE"
            self.logger.info(f"Refactoring application enabled [{mode}]")
        else:
            self.logger.info("Refactoring application disabled; running verification only")

        verified_suggestions = []
        verification_results = []

        # In auto-apply mode, we might want to apply all valid ones
        # For now, implementing the logic to try them one by one

        for i, suggestion in enumerate(suggestions):
            confidence_info = f" (confidence: {suggestion.confidence_score:.2f})" if suggestion.confidence_score is not None else ""
            self.logger.info(f"Processing suggestion {i+1}/{len(suggestions)}: {suggestion.proposed_class_name}{confidence_info}")

            # Pre-screening: skip very low confidence suggestions
            min_verification_confidence = app_config.get("min_verification_confidence", 0.0)
            if min_verification_confidence > 0.0 and suggestion.confidence_score is not None:
                if suggestion.confidence_score < min_verification_confidence:
                    self.logger.info(
                        f"Skipping verification for {suggestion.proposed_class_name} "
                        f"(confidence {suggestion.confidence_score:.2f} < threshold {min_verification_confidence})"
                    )
                    suggestion.verification_status = "skipped_low_confidence"
                    continue

            if not suggestion.new_class_code or not suggestion.modified_original_code:
                # Try JDT code generation for suggestions with names but no code
                # (e.g., auto-named fallback from NamingStage)
                if suggestion.cluster and suggestion.proposed_class_name:
                    self.logger.info(
                        f"Generating code for {suggestion.proposed_class_name} via JDT..."
                    )
                    try:
                        from genec.core.jdt_code_generator import JDTCodeGenerator
                        jdt = JDTCodeGenerator()
                        class_deps = context.get("class_deps")
                        generated = jdt.generate(
                            cluster=suggestion.cluster,
                            new_class_name=suggestion.proposed_class_name,
                            class_file=context.class_file,
                            repo_path=context.repo_path,
                            class_deps=class_deps,
                        )
                        suggestion.new_class_code = generated.new_class_code
                        suggestion.modified_original_code = generated.modified_original_code
                        self.logger.info(f"JDT code generation successful for {suggestion.proposed_class_name}")
                    except Exception as e:
                        self.logger.warning(
                            f"JDT code generation failed for {suggestion.proposed_class_name}: {e}"
                        )
                        suggestion.verification_status = "skipped_code_gen_failed"
                        continue
                else:
                    self.logger.warning(
                        f"Skipping {suggestion.proposed_class_name} (missing code and no cluster)"
                    )
                    suggestion.verification_status = "skipped_missing_code"
                    continue

            if should_apply:
                application_result = self.applicator.apply_refactoring(
                    suggestion,
                    original_class_file=context.class_file,
                    repo_path=context.repo_path,
                    dry_run=dry_run,
                )
                if not application_result.success:
                    self.logger.warning(
                        f"Failed to apply suggestion {suggestion.proposed_class_name}"
                    )
                    continue

            # Verify
            class_deps = context.get("class_deps")
            try:
                with open(context.class_file, encoding="utf-8") as f:
                    original_code = f.read()
            except Exception as e:
                self.logger.error(f"Failed to read original file: {e}")
                suggestion.verification_status = "skipped_read_error"
                continue
            
            verification_result = self.verification_engine.verify_refactoring(
                suggestion=suggestion,
                original_code=original_code,
                original_class_file=context.class_file,
                repo_path=context.repo_path,
                class_deps=class_deps,
            )
            is_valid = verification_result.is_valid
            verification_results.append(verification_result)

            if is_valid:
                self.logger.info(f"Suggestion {suggestion.proposed_class_name} verified successfully")
                verified_suggestions.append(suggestion)
                suggestion.verification_status = "verified"

                if should_apply and not auto_apply:
                    # Revert if not auto-applying (just checking verification)
                    self.logger.info("Reverting changes (auto-apply disabled)...")
                    self.applicator.revert_changes()
            else:
                self.logger.warning(f"Suggestion {suggestion.proposed_class_name} failed verification")
                suggestion.verification_status = "failed"
                # Always revert failed suggestions
                if should_apply:
                    self.applicator.revert_changes()

        rejected_suggestions = [s for s in suggestions if getattr(s, 'verification_status', None) == "failed"]
        context.results["rejected_suggestions"] = rejected_suggestions
        context.results["verified_suggestions"] = verified_suggestions
        context.results["verification_results"] = verification_results

        if context.recorder:
            context.recorder.end_stage("verification", {
                "total_suggestions": len(suggestions),
                "verified_count": len(verified_suggestions),
                "rejected_count": len(suggestions) - len(verified_suggestions),
                "verification_details": [
                    {
                        "name": getattr(vr, 'suggestion_id', i),
                        "syntactic_pass": getattr(vr, 'syntactic_pass', False),
                        "semantic_pass": getattr(vr, 'semantic_pass', False),
                        "behavioral_pass": getattr(vr, 'behavioral_pass', False),
                        "status": getattr(vr, 'status', 'unknown'),
                    }
                    for i, vr in enumerate(verification_results)
                ],
            })

        return True
