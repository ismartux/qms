from django.urls import path

from ui.admin_panel.views.dashboard import admin_dashboard
from ui.admin_panel.views.capas import (
    capa_management,
    capa_create,
    capa_edit
)
from ui.admin_panel.views.reports import (
    reports,
    generate_report
)
from ui.admin_panel.views.org import (
    company_list, company_create, company_edit,
    plant_list, plant_create, plant_edit,
    department_list, department_create, department_edit,
    shop_list, shop_create, shop_edit,
    line_list, line_create, line_edit,
    station_list, station_create, station_edit,
    product_list, product_create, product_edit,
)

app_name = "admin_panel"

urlpatterns = [
    # ================= DASHBOARD =================
    path("", admin_dashboard, name="admin_dashboard"),

    # ================= CAPA =================
    path("capas/", capa_management, name="admin_capas"),
    path("capas/create/", capa_create, name="capa_create"),
    path("capas/<uuid:capa_id>/edit/", capa_edit, name="capa_edit"),

    # ================= REPORTS =================
    path("reports/", reports, name="reports"),
    path("reports/generate/", generate_report, name="generate_report"),

    # ================= ORGANIZATION (CRU) =================
    # Companies
    path("companies/", company_list, name="company_list"),
    path("companies/create/", company_create, name="company_create"),
    path("companies/<int:pk>/edit/", company_edit, name="company_edit"),

    # Plants
    path("plants/", plant_list, name="plant_list"),
    path("plants/create/", plant_create, name="plant_create"),
    path("plants/<int:pk>/edit/", plant_edit, name="plant_edit"),

    # Departments
    path("departments/", department_list, name="department_list"),
    path("departments/create/", department_create, name="department_create"),
    path("departments/<int:pk>/edit/", department_edit, name="department_edit"),

    # Shops
    path("shops/", shop_list, name="shop_list"),
    path("shops/create/", shop_create, name="shop_create"),
    path("shops/<int:pk>/edit/", shop_edit, name="shop_edit"),

    # Lines
    path("lines/", line_list, name="line_list"),
    path("lines/create/", line_create, name="line_create"),
    path("lines/<int:pk>/edit/", line_edit, name="line_edit"),

    # Stations
    path("stations/", station_list, name="station_list"),
    path("stations/create/", station_create, name="station_create"),
    path("stations/<int:pk>/edit/", station_edit, name="station_edit"),

    # Products
    path("products/", product_list, name="product_list"),
    path("products/create/", product_create, name="product_create"),
    path("products/<int:pk>/edit/", product_edit, name="product_edit"),
]
