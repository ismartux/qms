import requests
from django.conf import settings


def create_user_bitable_record_via_relay(app_token, table_id, records):
    response = requests.post(
        settings.CLOUDFLARE_RELAY_URL,
        json={
            "app_token": app_token,
            "table_id": table_id,
            "records": records,
        },
        headers={
            "X-RELAY-SECRET": settings.CLOUDFLARE_RELAY_SECRET
        },
        timeout=20,
    )

    return response.json()


def create_bitable_record_via_relay(app_token, table_id, records):
    response = requests.post(
        settings.CLOUDFLARE_RELAY_URL,
        json={
            "app_token": app_token,
            "table_id": table_id,
            "records": records,
        },
        headers={
            "X-RELAY-SECRET": settings.CLOUDFLARE_RELAY_SECRET
        },
        timeout=20,
    )

    return response.json()