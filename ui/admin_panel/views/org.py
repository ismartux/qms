from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from ui.admin_panel.views.base import admin_required
from org.models import (
    Company,
    Plant,
    Floor,
    Department,
    Shop,
    Line,
    Station,
    Product,
    FloorTLAssignment,
    ShopPQEAssignment,
    IPQCMapping,
)
from ui.admin_panel.forms import (
    CompanyForm,
    PlantForm,
    FloorForm,
    DepartmentForm,
    ShopForm,
    LineForm,
    StationForm,
    ProductForm,
    FloorTLAssignmentForm,
    ShopPQEAssignmentForm,
    IPQCMappingForm,
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


# =========================================================
# FLOOR (CRU)
# =========================================================
@admin_required
def floor_list(request):
    search_query = request.GET.get("q", "").strip()
    floors = Floor.objects.select_related("plant").all()

    if search_query:
        floors = floors.filter(name__icontains=search_query) | floors.filter(code__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": floors,
        "entity_type": "floor",
        "title": "Floors",
        "search_query": search_query,
        "active_tab": "floors",
    })


@admin_required
def floor_create(request):
    form = FloorForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        floor = form.save()
        messages.success(request, f"Floor '{floor.name}' created successfully.")
        return redirect("admin_panel:floor_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create Floor",
        "entity_type": "floor",
        "back_url_name": "admin_panel:floor_list",
    })


@admin_required
def floor_edit(request, pk):
    floor = get_object_or_404(Floor, pk=pk)
    form = FloorForm(request.POST or None, instance=floor)

    if request.method == "POST" and form.is_valid():
        floor = form.save()
        messages.success(request, f"Floor '{floor.name}' updated successfully.")
        return redirect("admin_panel:floor_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": floor,
        "title": f"Edit Floor: {floor.name}",
        "entity_type": "floor",
        "back_url_name": "admin_panel:floor_list",
    })
# =========================================================
# FLOOR-WISE TL ASSIGNMENT (CRU)
# =========================================================
@admin_required
def floor_tl_list(request):
    search_query = request.GET.get("q", "").strip()
    assignments = FloorTLAssignment.objects.select_related("floor", "floor__plant", "user", "assigned_by").all()

    if search_query:
        assignments = assignments.filter(user__username__icontains=search_query) | assignments.filter(floor__name__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": assignments,
        "entity_type": "floor_tl",
        "title": "Floor-wise TL Assignments",
        "search_query": search_query,
        "active_tab": "floor_tls",
    })


@admin_required
def floor_tl_create(request):
    form = FloorTLAssignmentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.assigned_by = request.user
        assignment.save()
        messages.success(request, f"TL '{assignment.user.username}' assigned to floor '{assignment.floor.name}'.")
        return redirect("admin_panel:floor_tl_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Assign TL to Floor",
        "entity_type": "floor_tl",
        "back_url_name": "admin_panel:floor_tl_list",
    })


@admin_required
def floor_tl_edit(request, pk):
    assignment = get_object_or_404(FloorTLAssignment, pk=pk)
    form = FloorTLAssignmentForm(request.POST or None, instance=assignment)

    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        messages.success(request, f"Floor TL assignment for '{assignment.user.username}' updated.")
        return redirect("admin_panel:floor_tl_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": assignment,
        "title": f"Edit TL Assignment: {assignment.user.username} @ {assignment.floor.name}",
        "entity_type": "floor_tl",
        "back_url_name": "admin_panel:floor_tl_list",
    })


# =========================================================
# SHOP-WISE PQE ASSIGNMENT (CRU)
# =========================================================
@admin_required
def shop_pqe_list(request):
    search_query = request.GET.get("q", "").strip()
    assignments = ShopPQEAssignment.objects.select_related("shop", "shop__plant", "user", "assigned_by").all()

    if search_query:
        assignments = assignments.filter(user__username__icontains=search_query) | assignments.filter(shop__name__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": assignments,
        "entity_type": "shop_pqe",
        "title": "Shop-wise PQE Assignments",
        "search_query": search_query,
        "active_tab": "shop_pqes",
    })


@admin_required
def shop_pqe_create(request):
    form = ShopPQEAssignmentForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.assigned_by = request.user
        assignment.save()
        messages.success(request, f"PQE '{assignment.user.username}' assigned to shop '{assignment.shop.name}'.")
        return redirect("admin_panel:shop_pqe_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Assign PQE to Shop",
        "entity_type": "shop_pqe",
        "back_url_name": "admin_panel:shop_pqe_list",
    })


@admin_required
def shop_pqe_edit(request, pk):
    assignment = get_object_or_404(ShopPQEAssignment, pk=pk)
    form = ShopPQEAssignmentForm(request.POST or None, instance=assignment)

    if request.method == "POST" and form.is_valid():
        assignment = form.save()
        messages.success(request, f"Shop PQE assignment for '{assignment.user.username}' updated.")
        return redirect("admin_panel:shop_pqe_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": assignment,
        "title": f"Edit PQE Assignment: {assignment.user.username} @ {assignment.shop.name}",
        "entity_type": "shop_pqe",
        "back_url_name": "admin_panel:shop_pqe_list",
    })


# =========================================================
# IPQC MAPPING (CRU)
# =========================================================
@admin_required
def ipqc_mapping_list(request):
    search_query = request.GET.get("q", "").strip()
    mappings = IPQCMapping.objects.select_related(
        "user", "plant", "floor", "shop", "assigned_by"
    ).prefetch_related("lines").all()

    if search_query:
        mappings = mappings.filter(user__username__icontains=search_query) | mappings.filter(floor__name__icontains=search_query) | mappings.filter(shop__name__icontains=search_query)

    return render(request, "admin/org/org_list.html", {
        "items": mappings,
        "entity_type": "ipqc_mapping",
        "title": "IPQC Mappings (TL & PQE Linked)",
        "search_query": search_query,
        "active_tab": "ipqc_mappings",
    })


@admin_required
def ipqc_mapping_create(request):
    form = IPQCMappingForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        mapping = form.save(commit=False)
        mapping.assigned_by = request.user
        mapping.save()
        form.save_m2m()
        messages.success(request, f"IPQC mapping for '{mapping.user.username}' created.")
        return redirect("admin_panel:ipqc_mapping_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "title": "Create IPQC Mapping",
        "entity_type": "ipqc_mapping",
        "back_url_name": "admin_panel:ipqc_mapping_list",
    })


@admin_required
def ipqc_mapping_edit(request, pk):
    mapping = get_object_or_404(IPQCMapping, pk=pk)
    form = IPQCMappingForm(request.POST or None, instance=mapping)

    if request.method == "POST" and form.is_valid():
        mapping = form.save()
        messages.success(request, f"IPQC mapping for '{mapping.user.username}' updated.")
        return redirect("admin_panel:ipqc_mapping_list")

    return render(request, "admin/org/org_form.html", {
        "form": form,
        "instance": mapping,
        "title": f"Edit IPQC Mapping: {mapping.user.username}",
        "entity_type": "ipqc_mapping",
        "back_url_name": "admin_panel:ipqc_mapping_list",
    })

