from django.db import transaction
from ehs_engine.models import RiskAssessment


class RiskEngine:

    # =========================================================
    # RISK CATEGORY THRESHOLDS
    # =========================================================

    RISK_CATEGORIES = {
        (1, 7): "LOW",
        (8, 14): "MEDIUM",
        (15, 19): "HIGH",
        (20, 10_000): "CRITICAL",
    }

    AUTO_ESCALATE_CATEGORIES = {"CRITICAL"}

    # =========================================================
    # BASIC CALCULATION
    # =========================================================

    @classmethod
    def calculate_score(cls, likelihood: int, severity: int) -> int:
        if not likelihood or not severity:
            return 0
        return likelihood * severity

    @classmethod
    def determine_category(cls, score: int) -> str:
        for (min_val, max_val), label in cls.RISK_CATEGORIES.items():
            if min_val <= score <= max_val:
                return label
        return "LOW"

    # =========================================================
    # APPLY MANUAL RISK MATRIX
    # =========================================================

    @classmethod
    @transaction.atomic
    def apply_to_submission(cls, submission, likelihood: int, severity: int):

        score = cls.calculate_score(likelihood, severity)
        category = cls.determine_category(score)

        RiskAssessment.objects.update_or_create(
            submission=submission,
            defaults={
                "likelihood": likelihood,
                "severity": severity,
            }
        )

        cls._update_submission_risk(submission, score, category)

        return {
            "score": score,
            "category": category,
            "escalated": cls._auto_escalate(submission, category),
        }

    # =========================================================
    # AUTO CALCULATION FROM BOOLEAN NO RESPONSES
    # =========================================================

    @classmethod
    @transaction.atomic
    def recalculate_from_responses(cls, submission):

        total_score = 0

        responses = submission.responses.select_related("item")

        for response in responses:
            if response.value == "NO":
                total_score += response.item.severity_weight

        category = cls.determine_category(total_score)

        cls._update_submission_risk(submission, total_score, category)

        return {
            "score": total_score,
            "category": category,
        }

    # =========================================================
    # ESCALATION CHECK (ITEM LEVEL)
    # =========================================================

    @classmethod
    @transaction.atomic
    def check_item_escalation(cls, submission):

        responses = submission.responses.select_related("item")

        for response in responses:
            if (
                response.value == "NO"
                and response.item.escalate_on_no
            ):
                return cls._force_under_review(submission)

        return False

    # =========================================================
    # AUTO ESCALATE BASED ON RISK CATEGORY
    # =========================================================

    @classmethod
    def _auto_escalate(cls, submission, category):

        if category in cls.AUTO_ESCALATE_CATEGORIES:
            return cls._force_under_review(submission)

        return False

    # =========================================================
    # FORCE UNDER REVIEW
    # =========================================================

    @classmethod
    def _force_under_review(cls, submission):

        if submission.status not in (
            "UNDER_REVIEW",
            "APPROVED",
            "CLOSED",
        ):
            submission.status = "UNDER_REVIEW"
            submission.save(update_fields=["status"])
            return True

        return False

    # =========================================================
    # UPDATE SUBMISSION RISK (SAFE WRITE)
    # =========================================================

    @classmethod
    def _update_submission_risk(cls, submission, score, category):

        fields_to_update = []

        if submission.risk_score != score:
            submission.risk_score = score
            fields_to_update.append("risk_score")

        if submission.risk_category != category:
            submission.risk_category = category
            fields_to_update.append("risk_category")

        if fields_to_update:
            submission.save(update_fields=fields_to_update)

    # =========================================================
    # MASTER PROCESSOR
    # =========================================================

    @classmethod
    @transaction.atomic
    def process_submission(cls, submission):

        # Step 1: Recalculate risk
        risk_data = cls.recalculate_from_responses(submission)

        # Step 2: Check escalation rules
        item_escalated = cls.check_item_escalation(submission)

        # Step 3: Auto escalate by category
        category_escalated = cls._auto_escalate(
            submission,
            risk_data["category"]
        )

        return {
            "score": risk_data["score"],
            "category": risk_data["category"],
            "item_escalated": item_escalated,
            "category_escalated": category_escalated,
        }