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
    floor_list, floor_create, floor_edit,
    department_list, department_create, department_edit,
    shop_list, shop_create, shop_edit,
    line_list, line_create, line_edit,
    station_list, station_create, station_edit,
    product_list, product_create, product_edit,
    floor_tl_list, floor_tl_create, floor_tl_edit,
    shop_pqe_list, shop_pqe_create, shop_pqe_edit,
    ipqc_mapping_list, ipqc_mapping_create, ipqc_mapping_edit,
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

    # Floors
    path("floors/", floor_list, name="floor_list"),
    path("floors/create/", floor_create, name="floor_create"),
    path("floors/<int:pk>/edit/", floor_edit, name="floor_edit"),

    # Departments
    path("departments/", department_list, name="department_list"),
    path("departments/create/", department_create, name="department_create"),
    path("departments/<int:pk>/edit/", department_edit, name="department_edit"),

    # Shops (Sections)
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

    # ================= ASSIGNMENTS & MAPPINGS =================
    # Floor-wise TL
    path("floor-tls/", floor_tl_list, name="floor_tl_list"),
    path("floor-tls/create/", floor_tl_create, name="floor_tl_create"),
    path("floor-tls/<int:pk>/edit/", floor_tl_edit, name="floor_tl_edit"),

    # Shop-wise PQE
    path("shop-pqes/", shop_pqe_list, name="shop_pqe_list"),
    path("shop-pqes/create/", shop_pqe_create, name="shop_pqe_create"),
    path("shop-pqes/<int:pk>/edit/", shop_pqe_edit, name="shop_pqe_edit"),

    # IPQC Mapping
    path("ipqc-mappings/", ipqc_mapping_list, name="ipqc_mapping_list"),
    path("ipqc-mappings/create/", ipqc_mapping_create, name="ipqc_mapping_create"),
    path("ipqc-mappings/<int:pk>/edit/", ipqc_mapping_edit, name="ipqc_mapping_edit"),
]
