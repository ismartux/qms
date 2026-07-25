import json
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings


@csrf_exempt
def receive_bitable_snapshot(request):

    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    if request.headers.get("X-RELAY-SECRET") != settings.CLOUDFLARE_READ_RELAY_SECRET:
        return JsonResponse({"error": "unauthorized"}, status=403)

    try:
        payload = json.loads(request.body)
        template_id = payload["template_id"]
        rows = payload["rows"]
    except Exception as e:
        return JsonResponse({"error": "invalid_payload"}, status=400)


    cache_key = f"dynamic_forms:bitable_rows:{template_id}"
    cache.set(cache_key, rows, timeout=3600)


    return JsonResponse({
        "success": True,
        "template_id": template_id,
        "rows_count": len(rows),
    })