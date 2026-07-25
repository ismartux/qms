import operator
import re

from forms_engine.models import ChecklistItem


# =====================================================
# SAFE NUMERIC COMPARATORS
# =====================================================

COMPARATORS = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
}


def safe_numeric_compare(normalized_value, condition: str) -> bool:
    if normalized_value is None:
        return False

    try:
        normalized_value = float(normalized_value)
    except (TypeError, ValueError):
        return False

    condition = condition.strip()

    match = re.match(r"(>=|<=|>|<)\s*(-?\d+(\.\d+)?)$", condition)
    if not match:
        return False

    op_symbol = match.group(1)
    threshold = float(match.group(2))

    operation = COMPARATORS.get(op_symbol)
    if not operation:
        return False

    return operation(normalized_value, threshold)


# =====================================================
# VALUE NORMALIZATION
# =====================================================

def normalize_value(item: ChecklistItem, value):
    """
    Normalize value based on item type for rule comparison.
    """

    if value is None:
        return None

    item_type = item.item_type

    # BOOLEAN → YES / NO
    if item_type == "BOOLEAN":
        if isinstance(value, bool):
            return "YES" if value else "NO"
        return str(value).strip().upper()

    # TEXT → trimmed string
    if item_type == "TEXT":
        return str(value).strip()

    # NUMBER → numeric (float)
    if item_type == "NUMBER":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # DROPDOWN → normalized string
    if item.item_type == "DROPDOWN":
        return str(value).strip().upper()

    # PHOTO → presence check
    if item_type == "PHOTO":
        return bool(value)

    # Fallback
    return value


# =====================================================
# RULE CONDITION MATCHING
# =====================================================

def rule_matches(rule, normalized_value):
    """
    Determine whether a rule should trigger.
    """

    condition = rule.condition_value

    # No condition → always trigger
    if not condition:
        return True

    condition = condition.strip()

    # YES / NO comparison
    if condition.upper() in ("YES", "NO"):
        if normalized_value is None:
            return False
        return str(normalized_value).upper() == condition.upper()

    # Numeric comparison
    if re.match(r"^(>=|<=|>|<)", condition):
        return safe_numeric_compare(normalized_value, condition)

    # String equality (TEXT / DROPDOWN)
    return str(normalized_value) == condition


# =====================================================
# MAIN VALIDATION ENTRY
# =====================================================

def validate_response(item: ChecklistItem, value, payload: dict):
    """
    Validate a checklist item response against:
    - required flag
    - conditional rules (photo / remark)

    Raises ValueError with user-friendly message.
    """

    normalized_value = normalize_value(item, value)

    # -------------------------------------------------
    # REQUIRED FIELD CHECK
    # -------------------------------------------------
    if item.required:
        if normalized_value is None or normalized_value == "":
            raise ValueError(f"{item.label} is required")

    # -------------------------------------------------
    # CONDITIONAL RULE EVALUATION
    # -------------------------------------------------
    for rule in item.rules.all():

        if not rule_matches(rule, normalized_value):
            continue

        # -------------------------
        # PHOTO REQUIRED
        # -------------------------
        if rule.rule_type == "PHOTO_REQUIRED":
            if not payload.get("photo"):
                raise ValueError(
                    f"Photo required for '{item.label}'"
                )

        # -------------------------
        # REMARK REQUIRED
        # -------------------------
        if rule.rule_type == "REMARK_REQUIRED":
            remark = payload.get("remark")
            if remark is None or str(remark).strip() == "":
                raise ValueError(
                    f"Remark required for '{item.label}'"
                )