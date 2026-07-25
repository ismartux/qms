import requests
from django.conf import settings


def get_lark_access_token():
    url = (
        "https://open.larkoffice.com/open-apis/"
        "auth/v3/tenant_access_token/internal/"
    )

    payload = {
        "app_id": settings.LARK_APP_ID,
        "app_secret": settings.LARK_APP_SECRET,
    }

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()

    return response.json().get("tenant_access_token")
