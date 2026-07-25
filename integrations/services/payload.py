def build_payload(submission, mapping):
    """
    Build external integration payload safely.

    Optimized:
    - No N+1 queries
    - Null-safe
    - Transform-safe
    - Multi-plant safe
    """

    # -------------------------------------------------
    # 🔒 Prefetch responses in ONE query
    # -------------------------------------------------
    responses = {
        r.item_id: r
        for r in submission.responses.all()
    }

    payload = {}

    # -------------------------------------------------
    # 🔁 Field Mapping Loop
    # -------------------------------------------------
    for field in mapping.fields.all():

        response = responses.get(field.item_id)
        if not response:
            continue

        value = response.value

        # Null safety
        if value is None:
            continue

        # -------------------------------------------------
        # 🔄 Transform Handling
        # -------------------------------------------------
        if field.transform == "bool_to_yes_no":
            value_str = str(value).strip().upper()

            if value_str in ("YES", "TRUE", "1"):
                value = "YES"
            elif value_str in ("NO", "FALSE", "0"):
                value = "NO"
            else:
                value = ""

        payload[field.external_field] = value

    # -------------------------------------------------
    # 🔒 Submission Metadata (Null-safe)
    # -------------------------------------------------
    payload.update({
        "Submission ID": str(submission.submission_id),
        "Plant": submission.plant.name if submission.plant else "",
        "Line": submission.line.name if submission.line else "",
        "Product": submission.product.name if submission.product else "",
        "Severity": submission.severity_score or 0,
        "Submitted At": (
            submission.submitted_at.isoformat()
            if submission.submitted_at else ""
        ),
    })

    return payload