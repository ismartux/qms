from typing import Dict, Any

from django.core.exceptions import ValidationError

from submissions.models import DynamicFormSubmissionValue
from dynamic_forms.services.runtime_engine import DynamicFormRuntimeEngine
from dynamic_forms.models import DynamicFormVersion


def validate_dynamic_submission(
    submission,
    *,
    enforce_standards: bool = False,
):
    """
    Validates a dynamic form submission.

    - Hard rules are ALWAYS enforced
    - Standard rules are enforced ONLY if enforce_standards=True
    """

    version: DynamicFormVersion = submission.template_version

    engine = DynamicFormRuntimeEngine(
        version=version,
        preview=False,
    )

    schema = engine.build_runtime_schema()
    fields = schema["fields"]

    # -------------------------------------------------
    # COLLECT RESPONSES (DB VALUES)
    # -------------------------------------------------
    responses: Dict[str, Any] = {
        str(v.field_id): v.value
        for v in DynamicFormSubmissionValue.objects.filter(
            submission=submission
        )
    }

    errors = []

    # ---------------------------------------------
    # FIELD-LEVEL HARD VALIDATION
    # ---------------------------------------------
    for field in fields:
        field_id = str(field["id"])
        label = field["label"]
        field_type = field["type"]

        value = responses.get(field_id)

        # -------------------------------------------------
        # REQUIRED (IMAGE-SAFE)
        # -------------------------------------------------
        if field.get("required"):
            if field_type == "IMAGE":
                # IMAGE is stored as a file reference / path
                if not value:
                    errors.append(f"{label} is required")
                    continue
            else:
                if value in (None, "", []):
                    errors.append(f"{label} is required")
                    continue

        # -------------------------------------------------
        # DEPENDENCY (IMAGE-SAFE)
        # -------------------------------------------------
        dependency = field.get("dependency")
        if dependency:
            parent_id = str(dependency.get("depends_on"))
            parent_value = responses.get(parent_id)

            if parent_value not in (None, "", []):
                if field_type == "IMAGE":
                    if not value:
                        errors.append(
                            f"{label} is required when parent field is selected"
                        )
                        continue
                else:
                    if value in (None, "", []):
                        errors.append(
                            f"{label} is required when parent field is selected"
                        )
                        continue

        # -------------------------------------------------
        # NUMBER
        # -------------------------------------------------
        if field_type == "NUMBER" and value not in (None, ""):
            try:
                num_value = float(value)
            except (TypeError, ValueError):
                errors.append(f"{label} must be a number")
                continue

            min_v = field.get("min")
            max_v = field.get("max")

            if min_v is not None and num_value < float(min_v):
                errors.append(f"{label} must be ≥ {min_v}")

            if max_v is not None and num_value > float(max_v):
                errors.append(f"{label} must be ≤ {max_v}")

        # -------------------------------------------------
        # DROPDOWN
        # -------------------------------------------------
        if field_type == "DROPDOWN" and value not in (None, ""):
            options = field.get("options") or []
            if options and value not in options:
                errors.append(f"{label} has invalid value")

        # -------------------------------------------------
        # BOOLEAN
        # -------------------------------------------------
        if field_type == "BOOLEAN" and value not in (None, ""):
            if str(value).lower() not in {
                "true", "false", "yes", "no", "1", "0"
            }:
                errors.append(f"{label} must be Yes or No")

        # -------------------------------------------------
        # IMAGE (OPTIONAL EXTRA SAFETY)
        # -------------------------------------------------
        if field_type == "IMAGE" and value:
            # value should be a file path / URL / identifier
            if not isinstance(value, str):
                errors.append(f"{label} has invalid image value")

    # ---------------------------------------------
    # STANDARD RULES (OPTIONAL)
    # ---------------------------------------------
    if enforce_standards:
        rule_results = engine.evaluate_standard_rules(
            submission_values=responses
        )

        for r in rule_results:
            if not r["passed"]:
                errors.append(
                    (
                        f"Validation failed for '{r['field_label']}': "
                        f"value {r['actual']} must be "
                        f"{r['operator']} {r['standard']}"
                    )
                )

    if errors:
        raise ValidationError(errors)