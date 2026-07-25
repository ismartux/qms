from django.db import transaction
from django.core.exceptions import ValidationError

from ehs_engine.models import WorkflowActionLog


class WorkflowEngine:

    # =========================================================
    # STATE MAP (STRICT TRANSITIONS)
    # =========================================================

    ALLOWED_TRANSITIONS = {
        "DRAFT": ["SUBMITTED"],
        "SUBMITTED": ["UNDER_REVIEW", "APPROVED", "REJECTED"],
        "UNDER_REVIEW": ["APPROVED", "REJECTED"],
        "APPROVED": ["CLOSED"],
        "REJECTED": ["SUBMITTED"],
        "CLOSED": [],
    }

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================

    @staticmethod
    def _log_action(submission, action, user, comment=""):
        WorkflowActionLog.objects.create(
            submission=submission,
            action=action,
            performed_by=user,
            comment=comment,
        )

    @classmethod
    def _transition(cls, submission, new_status, user, comment=""):
        current = submission.status

        if new_status == current:
            return  # ignore duplicate transition

        allowed = cls.ALLOWED_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            raise ValidationError(
                f"Invalid transition from {current} to {new_status}"
            )

        submission.status = new_status
        submission.save(update_fields=["status"])

        cls._log_action(
            submission=submission,
            action=new_status,
            user=user,
            comment=comment,
        )

    # =========================================================
    # START WORKFLOW
    # =========================================================

    @classmethod
    @transaction.atomic
    def start_workflow(cls, submission):
        """
        Moves DRAFT → SUBMITTED
        """

        if submission.status == "SUBMITTED":
            return

        cls._transition(
            submission=submission,
            new_status="SUBMITTED",
            user=submission.reported_by,
            comment="Initial submission",
        )

    # =========================================================
    # APPROVE
    # =========================================================

    @classmethod
    @transaction.atomic
    def approve(cls, submission, user, comment=""):
        cls._transition(
            submission=submission,
            new_status="APPROVED",
            user=user,
            comment=comment,
        )

    # =========================================================
    # REJECT
    # =========================================================

    @classmethod
    @transaction.atomic
    def reject(cls, submission, user, comment=""):
        cls._transition(
            submission=submission,
            new_status="REJECTED",
            user=user,
            comment=comment,
        )

    # =========================================================
    # CLOSE
    # =========================================================

    @classmethod
    @transaction.atomic
    def close(cls, submission, user, comment=""):
        cls._transition(
            submission=submission,
            new_status="CLOSED",
            user=user,
            comment=comment,
        )

    # =========================================================
    # AUTO ESCALATE (CRITICAL RISK)
    # =========================================================

    @classmethod
    @transaction.atomic
    def auto_escalate_if_critical(cls, submission):
        """
        Escalates submission to UNDER_REVIEW if CRITICAL.
        """

        if submission.risk_category != "CRITICAL":
            return False

        if submission.status in ("UNDER_REVIEW", "APPROVED", "CLOSED"):
            return False

        cls._transition(
            submission=submission,
            new_status="UNDER_REVIEW",
            user=submission.reported_by,
            comment="Auto escalated due to CRITICAL risk",
        )

        return True

    # =========================================================
    # AUTO ESCALATE (RULE-BASED)
    # =========================================================

    @classmethod
    @transaction.atomic
    def auto_escalate_from_rules(cls, submission):
        """
        Escalates submission to UNDER_REVIEW due to rule trigger.
        """

        if submission.status in ("UNDER_REVIEW", "APPROVED", "CLOSED"):
            return False

        cls._transition(
            submission=submission,
            new_status="UNDER_REVIEW",
            user=submission.reported_by,
            comment="Auto escalated due to rule trigger",
        )

        return True