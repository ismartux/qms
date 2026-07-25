from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from ui.admin_panel.views.base import admin_required
from org.models import Company, Plant, Department, Shop, Line, Station, Product
from ui.admin_panel.forms import (
    CompanyForm,
    PlantForm,
    DepartmentForm,
    ShopForm,
    LineForm,
    StationForm,
    ProductForm,
)


# =========================================================
# COMPANY (CRU)
# =========================================================
@admin_required
def company_list(request):
    search_query = request.GET.get("q", "").strip()
    companies = Company.objects.all()

    if search_query:
        companies = companies.filter(name__icontains=search_query) | companies.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": companies,
        "entity_type": "company",
        "title": "Companies",
        "search_query": search_query,
        "active_tab": "companies",
    })


@admin_required
def company_create(request):
    form = CompanyForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(request, f"Company '{company.name}' created successfully.")
        return redirect("admin_panel:company_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Company",
        "entity_type": "company",
        "back_url_name": "admin_panel:company_list",
    })


@admin_required
def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    form = CompanyForm(request.POST or None, instance=company)

    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(request, f"Company '{company.name}' updated successfully.")
        return redirect("admin_panel:company_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": company,
        "title": f"Edit Company: {company.name}",
        "entity_type": "company",
        "back_url_name": "admin_panel:company_list",
    })


# =========================================================
# PLANT (CRU)
# =========================================================
@admin_required
def plant_list(request):
    search_query = request.GET.get("q", "").strip()
    plants = Plant.objects.select_related("company").all()

    if search_query:
        plants = plants.filter(name__icontains=search_query) | plants.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": plants,
        "entity_type": "plant",
        "title": "Plants",
        "search_query": search_query,
        "active_tab": "plants",
    })


@admin_required
def plant_create(request):
    form = PlantForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        plant = form.save()
        messages.success(request, f"Plant '{plant.name}' created successfully.")
        return redirect("admin_panel:plant_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Plant",
        "entity_type": "plant",
        "back_url_name": "admin_panel:plant_list",
    })


@admin_required
def plant_edit(request, pk):
    plant = get_object_or_404(Plant, pk=pk)
    form = PlantForm(request.POST or None, instance=plant)

    if request.method == "POST" and form.is_valid():
        plant = form.save()
        messages.success(request, f"Plant '{plant.name}' updated successfully.")
        return redirect("admin_panel:plant_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": plant,
        "title": f"Edit Plant: {plant.name}",
        "entity_type": "plant",
        "back_url_name": "admin_panel:plant_list",
    })


# =========================================================
# DEPARTMENT (CRU)
# =========================================================
@admin_required
def department_list(request):
    search_query = request.GET.get("q", "").strip()
    departments = Department.objects.select_related("plant").all()

    if search_query:
        departments = departments.filter(name__icontains=search_query) | departments.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": departments,
        "entity_type": "department",
        "title": "Departments",
        "search_query": search_query,
        "active_tab": "departments",
    })


@admin_required
def department_create(request):
    form = DepartmentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        dept = form.save()
        messages.success(request, f"Department '{dept.name}' created successfully.")
        return redirect("admin_panel:department_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Department",
        "entity_type": "department",
        "back_url_name": "admin_panel:department_list",
    })


@admin_required
def department_edit(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=dept)

    if request.method == "POST" and form.is_valid():
        dept = form.save()
        messages.success(request, f"Department '{dept.name}' updated successfully.")
        return redirect("admin_panel:department_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": dept,
        "title": f"Edit Department: {dept.name}",
        "entity_type": "department",
        "back_url_name": "admin_panel:department_list",
    })


# =========================================================
# SHOP (CRU)
# =========================================================
@admin_required
def shop_list(request):
    search_query = request.GET.get("q", "").strip()
    shops = Shop.objects.select_related("plant").all()

    if search_query:
        shops = shops.filter(name__icontains=search_query) | shops.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": shops,
        "entity_type": "shop",
        "title": "Shops",
        "search_query": search_query,
        "active_tab": "shops",
    })


@admin_required
def shop_create(request):
    form = ShopForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        shop = form.save()
        messages.success(request, f"Shop '{shop.name}' created successfully.")
        return redirect("admin_panel:shop_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Shop",
        "entity_type": "shop",
        "back_url_name": "admin_panel:shop_list",
    })


@admin_required
def shop_edit(request, pk):
    shop = get_object_or_404(Shop, pk=pk)
    form = ShopForm(request.POST or None, instance=shop)

    if request.method == "POST" and form.is_valid():
        shop = form.save()
        messages.success(request, f"Shop '{shop.name}' updated successfully.")
        return redirect("admin_panel:shop_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": shop,
        "title": f"Edit Shop: {shop.name}",
        "entity_type": "shop",
        "back_url_name": "admin_panel:shop_list",
    })


# =========================================================
# LINE (CRU)
# =========================================================
@admin_required
def line_list(request):
    search_query = request.GET.get("q", "").strip()
    lines = Line.objects.select_related("shop", "shop__plant").all()

    if search_query:
        lines = lines.filter(name__icontains=search_query) | lines.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": lines,
        "entity_type": "line",
        "title": "Lines",
        "search_query": search_query,
        "active_tab": "lines",
    })


@admin_required
def line_create(request):
    form = LineForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        line = form.save()
        messages.success(request, f"Line '{line.name}' created successfully.")
        return redirect("admin_panel:line_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Line",
        "entity_type": "line",
        "back_url_name": "admin_panel:line_list",
    })


@admin_required
def line_edit(request, pk):
    line = get_object_or_404(Line, pk=pk)
    form = LineForm(request.POST or None, instance=line)

    if request.method == "POST" and form.is_valid():
        line = form.save()
        messages.success(request, f"Line '{line.name}' updated successfully.")
        return redirect("admin_panel:line_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": line,
        "title": f"Edit Line: {line.name}",
        "entity_type": "line",
        "back_url_name": "admin_panel:line_list",
    })


# =========================================================
# STATION (CRU)
# =========================================================
@admin_required
def station_list(request):
    search_query = request.GET.get("q", "").strip()
    stations = Station.objects.select_related("line", "line__shop").all()

    if search_query:
        stations = stations.filter(name__icontains=search_query) | stations.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": stations,
        "entity_type": "station",
        "title": "Stations",
        "search_query": search_query,
        "active_tab": "stations",
    })


@admin_required
def station_create(request):
    form = StationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        station = form.save()
        messages.success(request, f"Station '{station.name}' created successfully.")
        return redirect("admin_panel:station_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Station",
        "entity_type": "station",
        "back_url_name": "admin_panel:station_list",
    })


@admin_required
def station_edit(request, pk):
    station = get_object_or_404(Station, pk=pk)
    form = StationForm(request.POST or None, instance=station)

    if request.method == "POST" and form.is_valid():
        station = form.save()
        messages.success(request, f"Station '{station.name}' updated successfully.")
        return redirect("admin_panel:station_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": station,
        "title": f"Edit Station: {station.name}",
        "entity_type": "station",
        "back_url_name": "admin_panel:station_list",
    })


# =========================================================
# PRODUCT (CRU)
# =========================================================
@admin_required
def product_list(request):
    search_query = request.GET.get("q", "").strip()
    products = Product.objects.select_related("company", "plant").all()

    if search_query:
        products = products.filter(name__icontains=search_query) | products.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": products,
        "entity_type": "product",
        "title": "Products",
        "search_query": search_query,
        "active_tab": "products",
    })


@admin_required
def product_create(request):
    form = ProductForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Product '{product.name}' created successfully.")
        return redirect("admin_panel:product_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Product",
        "entity_type": "product",
        "back_url_name": "admin_panel:product_list",
    })


@admin_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)

    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"Product '{product.name}' updated successfully.")
        return redirect("admin_panel:product_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": product,
        "title": f"Edit Product: {product.name}",
        "entity_type": "product",
        "back_url_name": "admin_panel:product_list",
    })
