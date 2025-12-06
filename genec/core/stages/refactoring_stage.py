from genec.core.refactoring_applicator import RefactoringApplicator
from genec.core.stages.base_stage import PipelineContext, PipelineStage
from genec.core.verification_engine import VerificationEngine
from genec.utils.progress_server import emit_progress


class RefactoringStage(PipelineStage):
    """Stage for applying and verifying refactorings."""

    def __init__(self, applicator: RefactoringApplicator, verification_engine: VerificationEngine):
        super().__init__("Refactoring")
        self.applicator = applicator
        self.verification_engine = verification_engine

    def run(self, context: PipelineContext) -> bool:
        app_config = context.config.get("refactoring_application", {})
        if not app_config.get("enabled", False):
            self.logger.info("Refactoring application disabled in config")
            return True

        emit_progress(6, 6, "Applying refactorings...")
        self.logger.info("\n[Stage 6/6] Applying and verifying refactorings...")

        suggestions = context.get("suggestions", [])
        if not suggestions:
            self.logger.info("No suggestions to apply")
            return True

        auto_apply = app_config.get("auto_apply", False)
        dry_run = app_config.get("dry_run", False)

        # If dry run, we don't actually apply/verify, just log
        if dry_run:
            self.logger.info("Dry run enabled - skipping actual application")
            return True

        verified_suggestions = []

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

            # Apply
            success = self.applicator.apply_refactoring(
                suggestion,
                original_class_file=context.class_file,
                repo_path=context.repo_path,
                dry_run=dry_run
            )
            if not success:
                self.logger.warning(f"Failed to apply suggestion {suggestion.proposed_class_name}")
                continue

            # Verify
            class_deps = context.get("class_deps")
            try:
                with open(context.class_file, encoding="utf-8") as f:
                    original_code = f.read()
            except Exception as e:
                self.logger.error(f"Failed to read original file: {e}")
                original_code = ""
            
            verification_result = self.verification_engine.verify_refactoring(
                suggestion=suggestion,
                original_code=original_code,
                original_class_file=context.class_file,
                repo_path=context.repo_path,
                class_deps=class_deps,
            )
            is_valid = verification_result.is_valid

            if is_valid:
                self.logger.info(f"Suggestion {suggestion.proposed_class_name} verified successfully")
                verified_suggestions.append(suggestion)
                suggestion.verification_status = "verified"

                if not auto_apply:
                    # Revert if not auto-applying (just checking verification)
                    self.logger.info("Reverting changes (auto-apply disabled)...")
                    self.applicator.revert_changes()
            else:
                self.logger.warning(f"Suggestion {suggestion.proposed_class_name} failed verification")
                suggestion.verification_status = "failed"
                # Always revert failed suggestions
                self.applicator.revert_changes()

        context.results["verified_suggestions"] = verified_suggestions
        return True
