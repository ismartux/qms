from django.utils import timezone
from django.conf import settings
from .cloudflare_client import create_bitable_record_via_relay


def sync_user_to_bitable(
    *,
    user,
    raw_password,
    scope=None,
    app_token,
    table_id,
    created_by=None,
):
    fields = {
        "Employee_ID": str(user.username),
        "First_Name": user.first_name or "",
        "Last_Name": user.last_name or "",
        "Email": user.email or "",
        "Password": raw_password,
        "Is_Active": str(user.is_active),
        "Is_Staff": str(user.is_staff),
        "Created_At": int(timezone.now().timestamp() * 1000),
    }

    if scope:
        fields.update({
            "Plant": scope.plant.name if scope.plant else "",
            "Department": scope.department.name if scope.department else "",
            "Role": scope.role.name if scope.role else "",
        })

    if created_by:
        fields["Created_By"] = created_by.username

    payload = {
        "app_token": app_token.strip(),
        "table_id": table_id.strip(),
        "records": [fields],   # 🔥 IMPORTANT — relay expects list
    }

    result = create_bitable_record_via_relay(
        app_token=payload["app_token"],
        table_id=payload["table_id"],
        records=payload["records"],
    )

    if not result.get("success"):
        raise Exception(f"Bitable write failed: {result}")

    return result
