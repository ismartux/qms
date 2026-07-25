def require_fields(data: dict, fields: list):
    """
    Ensure required keys exist in data.
    Does NOT validate emptiness (keeps existing behavior).
    """
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")

    missing = [field for field in fields if field not in data]

    if missing:
        raise ValueError(
            f"Missing required fields: {', '.join(map(str, missing))}"
        )


def validate_choice(value, allowed_values):
    """
    Ensure value is within allowed_values.
    Keeps strict comparison (no normalization to avoid breaking logic).
    """
    if allowed_values is None:
        raise ValueError("Allowed values cannot be None")

    if value not in allowed_values:
        allowed_str = ", ".join(map(str, allowed_values))
        raise ValueError(
            f"Invalid value '{value}'. Allowed values: {allowed_str}"
        )