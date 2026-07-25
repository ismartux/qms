from django.core.exceptions import ValidationError
from django.db import transaction


class RuleEngine:
    """
    Centralized validation logic for EHS responses.
    Keeps rule logic outside models.
    """

    # =========================================================
    # VALIDATE SINGLE RESPONSE
    # =========================================================

    @classmethod
    def validate_response(cls, response, enforce_required=False):
        """
        Validate one response against:
        - Required field (optional enforcement)
        - Rule conditions
        """

        errors = {}
        item = response.item

        # ------------------------------------------
        # REQUIRED VALIDATION (ONLY IF ENFORCED)
        # ------------------------------------------
        if enforce_required and item.required and not response.value:
            errors["value"] = "This field is required."

        # No value → no further rule validation needed
        if not response.value:
            if errors:
                raise ValidationError(errors)
            return True

        # ------------------------------------------
        # MATCH RULES BASED ON SELECTED VALUE
        # ------------------------------------------
        matching_rules = item.rules.filter(
            condition_value=response.value
        )

        for rule in matching_rules:

            # PHOTO REQUIRED
            if rule.rule_type == "PHOTO_REQUIRED":
                if not response.photo:
                    errors["photo"] = (
                        f"Photo required when answer is {response.value}"
                    )

            # REMARK REQUIRED
            if rule.rule_type == "REMARK_REQUIRED":
                if not response.remark:
                    errors["remark"] = (
                        f"Remark required when answer is {response.value}"
                    )

        if errors:
            raise ValidationError(errors)

        return True

    # =========================================================
    # VALIDATE FULL SUBMISSION
    # =========================================================

    @classmethod
    @transaction.atomic
    def validate_submission(cls, submission):
        """
        Validate all responses before final submission.
        Raises aggregated ValidationError if any rule fails.
        """

        errors = {}

        responses = (
            submission.responses
            .select_related("item")
            .prefetch_related("item__rules")
        )

        # Validate existing responses
        for response in responses:
            try:
                cls.validate_response(
                    response,
                    enforce_required=True   # 🔥 REQUIRED enforced only here
                )
            except ValidationError as e:
                errors[response.item.label] = e.message_dict

        # Ensure required items exist at all
        sections = submission.version.sections.prefetch_related("items")

        for section in sections:
            for item in section.items.all():
                if item.required:
                    if not submission.responses.filter(item=item).exists():
                        errors[item.label] = {
                            "value": "Required item missing from submission."
                        }

        if errors:
            raise ValidationError(errors)

        return True

    # =========================================================
    # ESCALATION CHECK
    # =========================================================

    @classmethod
    def should_escalate(cls, submission):

        responses = (
            submission.responses
            .select_related("item")
            .prefetch_related("item__rules")
        )

        for response in responses:

            if not response.value:
                continue

            if response.item.rules.filter(
                rule_type="ESCALATE",
                condition_value=response.value
            ).exists():
                return True

        return False

    # =========================================================
    # GET ESCALATION ITEMS
    # =========================================================

    @classmethod
    def get_escalation_items(cls, submission):

        triggered = []

        responses = (
            submission.responses
            .select_related("item")
            .prefetch_related("item__rules")
        )

        for response in responses:
            if not response.value:
                continue

            if response.item.rules.filter(
                rule_type="ESCALATE",
                condition_value=response.value
            ).exists():
                triggered.append(response.item.label)

        return triggered