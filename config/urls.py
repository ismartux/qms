from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from config.serviceworker import ServiceWorkerView
from config.mainfest_service import manifest
from config.views import OfflineView

urlpatterns = [
    path("admin/", admin.site.urls),

    path("admin_panel/", include("ui.admin_panel.urls")),

    # AUTH
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),

    # APP
    path("", include("ui.urls")),
    path("api/", include("submissions.api.urls")),
    path("transs_admin_flow/", include("forms_engine.urls")),
    path("service_worker.js", ServiceWorkerView.as_view(), name="service_worker"),
    path("manifest.json", manifest, name="manifest"),
    path("offline/", OfflineView.as_view(), name="offline"),

    path("capa/", include("capa.urls", namespace="capa")),
    path("bitable/", include("integrations.urls", namespace="bitable")),

    path("dashboard/", include("analytics.urls")),
    path("ehs/", include("ehs_engine.urls")),
    path("ehs/builder/", include("ehs_engine.urls_builder")),
    path("dynamic_forms_admin/", include("dynamic_forms.admin_views.urls")),
    path("dynamic_forms/", include("dynamic_forms.urls")),

    path("scheduler/", include("scheduler.urls", namespace="scheduler_admin")),
    path("identity/", include("core.identity.urls", namespace="identity")),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
