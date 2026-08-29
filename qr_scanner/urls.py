from django.urls import path
from . import views

app_name = "qr_scanner"

urlpatterns = [
    # QR Scan page
    path("", views.qr_scan_view, name="qr_scan"),

    # AJAX: save scan result
    path("save/", views.qr_scan_save, name="qr_scan_save"),

    # Report / dashboard
    path("report/", views.qr_scan_report_view, name="qr_scan_report"),

    # CSV export
    path("export/", views.qr_scan_export, name="qr_scan_export"),

    # TTS proxy - Indian female voice (Google Translate en-IN)
    path("tts/", views.tts_proxy, name="tts_proxy"),
]
