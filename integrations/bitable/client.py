import requests
from .auth import get_lark_access_token


def create_bitable_record(app_token, table_id, fields):
    token = get_lark_access_token()

    url = (
        "https://open.larkoffice.com/open-apis/bitable/v1/apps/"
        f"{app_token}/tables/{table_id}/records"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {"fields": fields}

    response = requests.post(url, headers=headers, json=payload, timeout=10)


    try:
        data = response.json()
    except Exception:
        return False, "INVALID_JSON_RESPONSE"

    if response.status_code == 200 and data.get("code") == 0:
        return True, data["data"]["record"]["record_id"]

    return False, data