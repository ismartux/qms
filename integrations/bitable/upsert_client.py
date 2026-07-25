import requests
from django.conf import settings


def upsert_bitable_record_via_relay(
    *,
    app_token: str,
    table_id: str,
    records: list,
    match_field: str,
):
    response = requests.post(
        settings.CLOUDFLARE_UPSERT_RELAY_URL,
        json={
            "app_token": app_token,
            "table_id": table_id,
            "records": records,
            "match_field": match_field,
        },
        headers={
            "X-RELAY-SECRET": settings.CLOUDFLARE_UPSERT_RELAY_SECRET
        },
        timeout=20,
    )

    try:
        data = response.json()
    except Exception:
        raise Exception(
            f"Invalid JSON from relay | "
            f"HTTP {response.status_code} | "
            f"Body: {response.text}"
        )

    if not response.ok:
        raise Exception(
            f"HTTP {response.status_code} | Response: {data}"
        )

    if not data.get("success"):
        raise Exception(
            f"Relay reported failure: {data}"
        )

    return {
        "http_status": response.status_code,
        "response": data,
    }