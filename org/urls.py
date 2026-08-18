from django.urls import path
from org import views

app_name = "org"

urlpatterns = [
    # Dashboard
    path("", views.org_dashboard, name="dashboard"),
    
    # Companies
    path("companies/", views.company_list, name="company_list"),
    path("companies/add/", views.company_create, name="company_create"),
    path("companies/edit/<int:pk>/", views.company_edit, name="company_edit"),
    path("companies/delete/<int:pk>/", views.company_delete, name="company_delete"),
    
    # Plants
    path("plants/", views.plant_list, name="plant_list"),
    path("plants/add/", views.plant_create, name="plant_create"),
    path("plants/edit/<int:pk>/", views.plant_edit, name="plant_edit"),
    path("plants/delete/<int:pk>/", views.plant_delete, name="plant_delete"),
    
    # Departments
    path("departments/", views.department_list, name="department_list"),
    path("departments/add/", views.department_create, name="department_create"),
    path("departments/edit/<int:pk>/", views.department_edit, name="department_edit"),
    path("departments/delete/<int:pk>/", views.department_delete, name="department_delete"),
    
    # Shops
    path("shops/", views.shop_list, name="shop_list"),
    path("shops/add/", views.shop_create, name="shop_create"),
    path("shops/edit/<int:pk>/", views.shop_edit, name="shop_edit"),
    path("shops/delete/<int:pk>/", views.shop_delete, name="shop_delete"),
    
    # Lines
    path("lines/", views.line_list, name="line_list"),
    path("lines/add/", views.line_create, name="line_create"),
    path("lines/edit/<int:pk>/", views.line_edit, name="line_edit"),
    path("lines/delete/<int:pk>/", views.line_delete, name="line_delete"),
    
    # Stations
    path("stations/", views.station_list, name="station_list"),
    path("stations/add/", views.station_create, name="station_create"),
    path("stations/edit/<int:pk>/", views.station_edit, name="station_edit"),
    path("stations/delete/<int:pk>/", views.station_delete, name="station_delete"),
    
    # Products
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_create, name="product_create"),
    path("products/edit/<int:pk>/", views.product_edit, name="product_edit"),
    path("products/delete/<int:pk>/", views.product_delete, name="product_delete"),
    
    # AJAX endpoints for dynamic dropdowns
    path("ajax/plants/", views.ajax_get_plants, name="ajax_plants"),
    path("ajax/departments/", views.ajax_get_departments, name="ajax_departments"),
    path("ajax/shops/", views.ajax_get_shops, name="ajax_shops"),
    path("ajax/lines/", views.ajax_get_lines, name="ajax_lines"),
    path("ajax/stations/", views.ajax_get_stations, name="ajax_stations"),
]