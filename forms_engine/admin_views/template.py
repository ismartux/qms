from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from forms_engine.decorators import admin_required

from org.models import Plant, Product, Shop, Department
from forms_engine.models import ChecklistTemplate
from core.tenant.context import get_current_plant


# =====================================================
# CREATE TEMPLATE (ADMIN)
# =====================================================
@login_required
@admin_required
def create_template(request):

    current_plant = get_current_plant()

    if request.user.is_superuser:
        plants_qs = Plant.objects.all()
        products_qs = Product.objects.all()
        shops_qs = Shop.objects.all()
        departments_qs = Department.objects.select_related("plant").order_by("name")
    else:
        if not current_plant:
            return HttpResponseForbidden("Plant context required")

        plants_qs = Plant.objects.filter(id=current_plant.id)
        products_qs = Product.objects.filter(plant=current_plant)
        shops_qs = Shop.objects.filter(plant=current_plant)
        departments_qs = (
            Department.objects
            .filter(plant=current_plant)
            .select_related("plant")
            .order_by("name")
        )

    if request.method == "POST":

        department_id = request.POST.get("department")
        approval_flow = request.POST.get("approval_flow")

        if not department_id or not approval_flow:
            return HttpResponseForbidden("Department and approval flow required")

        if request.user.is_superuser:
            department = get_object_or_404(Department, id=department_id)
        else:
            department = get_object_or_404(
                Department,
                id=department_id,
                plant=current_plant
            )

        with transaction.atomic():

            template = ChecklistTemplate.objects.create(
                code=request.POST.get("code", "").strip(),
                name=request.POST.get("name", "").strip(),
                description=request.POST.get("description", "").strip(),
                department=department,
                approval_flow=approval_flow,
                is_active=request.POST.get("is_active") == "on",
                bitable_app_token=request.POST.get("bitable_app_token", "").strip(),
                bitable_table_id=request.POST.get("bitable_table_id", "").strip(),
            )

            if request.user.is_superuser:
                template.plants.set(
                    Plant.objects.filter(id__in=request.POST.getlist("plants"))
                )
            else:
                template.plants.set([current_plant])

            template.products.set(
                Product.objects.filter(id__in=request.POST.getlist("products"))
            )

            template.shops.set(
                Shop.objects.filter(id__in=request.POST.getlist("shops"))
            )

        return redirect(
            "transs_admin_flow:assign_roles",
            template_id=template.id
        )

    return render(
        request,
        "forms_builder/template_form.html",
        {
            "plants": plants_qs,
            "products": products_qs,
            "shops": shops_qs,
            "departments": departments_qs,
            "approval_flow_choices": ChecklistTemplate.APPROVAL_FLOW_CHOICES,
            "mode": "create",
            "has_published_version": False,
        },
    )


# =====================================================
# TEMPLATE DETAIL (ADMIN)
# =====================================================
@login_required
@admin_required
def template_detail(request, template_id):

    current_plant = get_current_plant()

    qs = (
        ChecklistTemplate.objects
        .prefetch_related(
            "versions",
            "plants",
            "products",
            "shops",
            "role_assignments__role",
        )
        .select_related("department")
    )

    if not request.user.is_superuser:
        qs = qs.filter(plants=current_plant)

    template = get_object_or_404(qs, id=template_id)

    return render(
        request,
        "forms_builder/template_detail.html",
        {
            "template": template,
        },
    )


# =====================================================
# EDIT TEMPLATE (ADMIN) ✅ FIXED
# =====================================================
@login_required
@admin_required
def edit_template(request, template_id):

    current_plant = get_current_plant()

    qs = ChecklistTemplate.objects.all()
    if not request.user.is_superuser:
        qs = qs.filter(plants=current_plant)

    template = get_object_or_404(qs, id=template_id)
    has_published_version = template.versions.filter(is_published=True).exists()

    if request.method == "POST":
        with transaction.atomic():

            # 🔒 Published version → only toggle active
            if has_published_version:
                template.is_active = request.POST.get("is_active") == "on"
                template.save(update_fields=["is_active"])
                return redirect("transs_admin_flow:form_builder_dashboard")

            # Base fields
            template.code = request.POST.get("code", "").strip()
            template.name = request.POST.get("name", "").strip()
            template.description = request.POST.get("description", "").strip()
            template.bitable_app_token = request.POST.get("bitable_app_token", "").strip()
            template.bitable_table_id = request.POST.get("bitable_table_id", "").strip()
            template.approval_flow = request.POST.get("approval_flow", "").strip()
            template.is_active = request.POST.get("is_active") == "on"
            template.save()

            # Plants FIRST
            if request.user.is_superuser:
                plant_ids = request.POST.getlist("plants")
                if plant_ids:
                    template.plants.set(Plant.objects.filter(id__in=plant_ids))
                else:
                    template.plants.clear()
            else:
                template.plants.set([current_plant])

            # Products
            template.products.set(
                Product.objects.filter(
                    id__in=request.POST.getlist("products")
                )
            )

            # ✅ SHOPS — FINAL FIX (NO plant filter)
            template.shops.clear()
            template.shops.set(
                Shop.objects.filter(
                    id__in=request.POST.getlist("shops")
                )
            )

        print("POST SHOPS:", request.POST.getlist("shops"))
        print("DB SHOPS:", list(template.shops.values_list("id", flat=True)))

        return redirect("transs_admin_flow:form_builder_dashboard")

    # GET
    if request.user.is_superuser:
        plants_qs = Plant.objects.all()
        products_qs = Product.objects.all()
        shops_qs = Shop.objects.all()
        departments_qs = Department.objects.select_related("plant").order_by("name")
    else:
        plants_qs = Plant.objects.filter(id=current_plant.id)
        products_qs = Product.objects.filter(plant=current_plant)
        shops_qs = Shop.objects.filter(plant=current_plant)
        departments_qs = (
            Department.objects
            .filter(plant=current_plant)
            .select_related("plant")
            .order_by("name")
        )

    return render(
        request,
        "forms_builder/template_form.html",
        {
            "template": template,
            "plants": plants_qs,
            "products": products_qs,
            "shops": shops_qs,
            "departments": departments_qs,
            "approval_flow_choices": ChecklistTemplate.APPROVAL_FLOW_CHOICES,
            "mode": "edit",
            "has_published_version": has_published_version,
        },
    )


# =====================================================
# ARCHIVE TEMPLATE
# =====================================================
@login_required
@admin_required
def archive_template(request, template_id):

    current_plant = get_current_plant()

    qs = ChecklistTemplate.objects.all()

    if not request.user.is_superuser:
        qs = qs.filter(plants=current_plant)

    template = get_object_or_404(qs, id=template_id)

    template.is_active = False
    template.is_archived = True
    template.save(update_fields=["is_active", "is_archived"])

    return redirect("transs_admin_flow:form_builder_dashboard")