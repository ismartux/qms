from django.db import transaction
from django.core.exceptions import ValidationError

from ehs_engine.services.risk_engine import RiskEngine
from ehs_engine.services.workflow_engine import WorkflowEngine
from ehs_engine.services.notification_service import NotificationService
from ehs_engine.services.rule_engine import RuleEngine


class SubmissionService:

    @staticmethod
    @transaction.atomic
    def process_submission(
        submission,
        likelihood: int = None,
        severity: int = None,
        use_matrix: bool = False
    ):
        """
        Master submission processor.

        Flow:
        1️⃣ Validate all rules
        2️⃣ Apply risk scoring
        3️⃣ Apply escalation logic
        4️⃣ Start workflow (if applicable)
        5️⃣ Auto escalate workflow if critical
        6️⃣ Notify reporter
        """

        # ==================================================
        # 1️⃣ VALIDATE RULES
        # ==================================================
        RuleEngine.validate_submission(submission)

        # ==================================================
        # 2️⃣ RISK PROCESSING
        # ==================================================
        if use_matrix:
            if likelihood is None or severity is None:
                raise ValidationError(
                    "Likelihood and severity required for matrix scoring."
                )

            risk_result = RiskEngine.apply_to_submission(
                submission,
                likelihood,
                severity
            )
        else:
            risk_result = RiskEngine.process_submission(submission)

        score = risk_result.get("score", 0)
        category = risk_result.get("category", "LOW")

        # ==================================================
        # 3️⃣ RULE-BASED ESCALATION
        # ==================================================
        rule_escalated = RuleEngine.should_escalate(submission)

        if rule_escalated:
            submission.status = "UNDER_REVIEW"
            submission.save(update_fields=["status"])

        # ==================================================
        # 4️⃣ START WORKFLOW
        # ==================================================
        WorkflowEngine.start_workflow(submission)

        # ==================================================
        # 5️⃣ AUTO WORKFLOW ESCALATION (CRITICAL)
        # ==================================================
        WorkflowEngine.auto_escalate_if_critical(submission)

        # ==================================================
        # 6️⃣ NOTIFY REPORTER
        # ==================================================
        NotificationService.notify_submission_created(submission)

        # ==================================================
        # RETURN STRUCTURED RESULT
        # ==================================================
        return {
            "score": score,
            "category": category,
            "rule_escalated": rule_escalated,
            "risk_category": submission.risk_category,
            "final_status": submission.status,
        }