import csv
import json
import urllib.request
import urllib.parse
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import (
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.identity.permissions import has_permission
from core.context import get_current_plant

from .models import QRScanSession


# =====================================================
# Permission helper
# =====================================================

def _has_scanner_access(user):
    """Return True if user is superuser or has can_access_qr_scanner permission."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return has_permission(user, "can_access_qr_scanner")


def _resolve_plant(request):
    """Best-effort plant resolution from user scope."""
    if request.user.is_superuser:
        return None
    try:
        return get_current_plant(request)
    except Exception:
        return None


# =====================================================
# QR Scan Page
# =====================================================

@login_required
def qr_scan_view(request):
    if not _has_scanner_access(request.user):
        return HttpResponseForbidden("Access denied: QR Scanner permission required.")
    return render(request, "scanner/qr_scan.html", {
        "page_title": "QR Scanner",
    })


# =====================================================
# Save Scan Result (AJAX POST)
# =====================================================

@login_required
@require_POST
def qr_scan_save(request):
    if not _has_scanner_access(request.user):
        return JsonResponse({"error": "Access denied"}, status=403)

    try:
        data = json.loads(request.body)
        qr1 = (data.get("qr_code_1") or "").strip()
        qr2 = (data.get("qr_code_2") or "").strip()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if not qr1 or not qr2:
        return JsonResponse({"error": "Both QR codes are required"}, status=400)

    is_match = (qr1 == qr2)
    plant = _resolve_plant(request)

    session = QRScanSession.objects.create(
        scanned_by=request.user,
        qr_code_1=qr1,
        qr_code_2=qr2,
        is_match=is_match,
        plant=plant,
    )

    return JsonResponse({
        "id": session.id,
        "result": session.result,
        "is_match": is_match,
        "scanned_at": session.scanned_at.isoformat(),
    })


# =====================================================
# QR Scan Report / Dashboard
# =====================================================

@login_required
def qr_scan_report_view(request):
    if not _has_scanner_access(request.user):
        return HttpResponseForbidden("Access denied: QR Scanner permission required.")

    # ------ Filters ------
    today = date.today()
    date_from_str = request.GET.get("date_from", "")
    date_to_str   = request.GET.get("date_to", "")
    result_filter = request.GET.get("result", "")      # PASS | FAIL | ""
    search        = request.GET.get("search", "").strip()

    # Defaults: last 7 days
    try:
        date_from = date.fromisoformat(date_from_str)
    except ValueError:
        date_from = today - timedelta(days=6)

    try:
        date_to = date.fromisoformat(date_to_str)
    except ValueError:
        date_to = today

    qs = QRScanSession.objects.select_related("scanned_by", "plant").all()

    # Date range (inclusive)
    qs = qs.filter(scanned_at__date__gte=date_from, scanned_at__date__lte=date_to)

    if result_filter in ("PASS", "FAIL"):
        qs = qs.filter(result=result_filter)

    if search:
        qs = qs.filter(qr_code_1__icontains=search) | \
             QRScanSession.objects.filter(qr_code_2__icontains=search,
                                          scanned_at__date__gte=date_from,
                                          scanned_at__date__lte=date_to)
        if result_filter in ("PASS", "FAIL"):
            qs = qs.filter(result=result_filter)

    qs = qs.order_by("-scanned_at")

    # ------ KPI Stats (over filtered date range) ------
    all_in_range = QRScanSession.objects.filter(
        scanned_at__date__gte=date_from,
        scanned_at__date__lte=date_to,
    )
    total_scans   = all_in_range.count()
    total_pass    = all_in_range.filter(result="PASS").count()
    total_fail    = all_in_range.filter(result="FAIL").count()
    pass_rate     = round((total_pass / total_scans * 100), 1) if total_scans else 0

    # ------ Pagination ------
    paginator = Paginator(qs, 25)
    page_num  = request.GET.get("page", 1)
    page_obj  = paginator.get_page(page_num)

    return render(request, "scanner/qr_scan_report.html", {
        "page_title": "Scanner Report",
        "page_obj": page_obj,
        "sessions": page_obj.object_list,
        # KPIs
        "total_scans": total_scans,
        "total_pass": total_pass,
        "total_fail": total_fail,
        "pass_rate": pass_rate,
        # Filters
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "result_filter": result_filter,
        "search": search,
    })


# =====================================================
# Export CSV
# =====================================================

@login_required
def qr_scan_export(request):
    if not _has_scanner_access(request.user):
        return HttpResponseForbidden("Access denied: QR Scanner permission required.")

    date_from_str = request.GET.get("date_from", "")
    date_to_str   = request.GET.get("date_to", "")
    result_filter = request.GET.get("result", "")

    today = date.today()
    try:
        date_from = date.fromisoformat(date_from_str)
    except ValueError:
        date_from = today - timedelta(days=6)
    try:
        date_to = date.fromisoformat(date_to_str)
    except ValueError:
        date_to = today

    qs = QRScanSession.objects.select_related("scanned_by", "plant").filter(
        scanned_at__date__gte=date_from,
        scanned_at__date__lte=date_to,
    )
    if result_filter in ("PASS", "FAIL"):
        qs = qs.filter(result=result_filter)

    qs = qs.order_by("-scanned_at")

    response = HttpResponse(content_type="text/csv")
    filename = f"qr_scan_report_{date_from}_{date_to}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        "ID", "Scanned At", "Scanned By", "QR Code 1", "QR Code 2", "Result", "Plant"
    ])

    for s in qs:
        writer.writerow([
            s.id,
            s.scanned_at.strftime("%Y-%m-%d %H:%M:%S"),
            s.scanned_by.username if s.scanned_by else "—",
            s.qr_code_1,
            s.qr_code_2,
            s.result,
            s.plant.name if s.plant else "—",
        ])

    return response


# =====================================================
# TTS Proxy — Google Translate Indian Female Voice
# =====================================================

@login_required
def tts_proxy(request):
    """
    Server-side proxy for Google Translate TTS (en-IN = Indian English).
    Avoids browser CORS, returns natural Indian female voice as audio/mpeg.

    GET /scanner/tts/?text=Pass
    """
    if not _has_scanner_access(request.user):
        return HttpResponseForbidden("Access denied")

    text = (request.GET.get("text") or "").strip()[:40]
    if not text:
        return HttpResponse(status=400)

    encoded = urllib.parse.quote(text)
    tts_url = (
        "https://translate.google.com/translate_tts"
        f"?ie=UTF-8&q={encoded}&tl=en-IN&client=tw-ob"
    )

    try:
        req = urllib.request.Request(
            tts_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://translate.google.com/",
                "Accept": "audio/mpeg, audio/*",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            audio_data = resp.read()

        response = HttpResponse(audio_data, content_type="audio/mpeg")
        response["Cache-Control"] = "public, max-age=3600"
        return response

    except Exception as exc:
        # 503 -> frontend falls back to Web Speech API
        return HttpResponse(f"TTS unavailable: {exc}", status=503)
