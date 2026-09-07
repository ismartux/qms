from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django import forms
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Case, When, Value, IntegerField, Q

from analytics.services.capa_analytics import CapaAnalyticsService

from core.identity.models import UserScope
from capa.models import CAPA
from core.identity.permissions import has_permission
from submissions.assignment_resolver import (
    filter_capas_for_pqe_scope,
    can_pqe_view_or_approve_capa,
)
from capa.services import (
    assign_capa,
    mark_action_done,
    close_capa,
    reject_capa,
)


# =========================================================
# HELPERS
# =========================================================

def user_in_role_for_capa(user, capa, role_field):
    role = getattr(capa, role_field)
    if not role:
        return False

    return UserScope.objects.filter(
        user=user,
        plant=capa.submission.work_context.plant,
        role=role
    ).exists()


def is_pqe(user):
    return has_permission(user, "can_manage_capa")


# =========================================================
# CAPA LIST VIEW
# =========================================================

@login_required
def capa_list_view(request):

    base_queryset = CAPA.objects.select_related(
        "submission",
        "submission__work_context__plant",
        "submission__work_context__product",
        "submission__work_context__line",
        "submission__work_context__shop",
        "submission__template_version__template",
        "rca_role",
        "capa_role",
    )

    if not request.user.is_superuser:
        plant_ids = request.user.scopes.values_list("plant_id", flat=True)
        base_queryset = base_queryset.filter(
            submission__work_context__plant_id__in=plant_ids
        )
        base_queryset = filter_capas_for_pqe_scope(request.user, base_queryset)

    today = timezone.now().date()

    capas = base_queryset.annotate(
        closed_order=Case(
            When(status="CLOSED", then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        overdue_order=Case(
            When(
                status__in=["OPEN", "ASSIGNED", "REJECTED", "ACTION_DONE"],
                due_date__lt=today,
                then=Value(0),
            ),
            When(status="CLOSED", then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by(
        "closed_order",
        "overdue_order",
        "due_date",
        "-created_at"
    )

    return render(request, "capa/capa_list.html", {
        "capas": capas,
        "today": today,
    })


# =========================================================
# POPUP VIEW
# =========================================================

@login_required
def capa_popup_view(request, capa_id):

    capa = get_object_or_404(
        CAPA.objects.select_related(
            "submission",
            "submission__template_version__template",
            "submission__work_context__line",
            "submission__work_context__product",
            "submission__work_context__plant",
            "submission__work_context__shop",
            "submission__submitted_by",
            "rca_role",
            "capa_role",
        ).prefetch_related(
            "submission__responses",
            "submission__attachments",
        ),
        capa_id=capa_id
    )

    if not request.user.is_superuser and is_pqe(request.user):
        if not can_pqe_view_or_approve_capa(request.user, capa):
            raise PermissionDenied

    submission = capa.submission

    sections = (
        submission.template_version.sections
        .prefetch_related("items")
        .order_by("order")
    )

    nc_responses_qs = submission.responses.filter(
        is_non_conformance=True
    )

    responses = {str(r.item_id): r for r in nc_responses_qs}

    return render(request, "capa/capa_popup.html", {
        "capa": capa,
        "submission": submission,
        "sections": sections,
        "responses": responses,
        "nc_count": nc_responses_qs.count(),
        "today": timezone.now().date(),
    })


# =========================================================
# FORM
# =========================================================

class CAPAUpdateForm(forms.ModelForm):
    class Meta:
        model = CAPA
        fields = ["rca_summary", "capa_plan"]
        widgets = {
            "rca_summary": forms.Textarea(attrs={
                "class": "w-full rounded-xl border px-4 py-3",
                "rows": 4
            }),
            "capa_plan": forms.Textarea(attrs={
                "class": "w-full rounded-xl border px-4 py-3",
                "rows": 4
            }),
        }


# =========================================================
# CAPA DETAIL (ASSIGNMENT - PQE)
# =========================================================

@login_required
def capa_detail_view(request, capa_id):

    capa = get_object_or_404(
        CAPA.objects.select_related(
            "submission",
            "submission__work_context__line",
            "submission__work_context__plant",
            "submission__work_context__shop",
        ),
        capa_id=capa_id
    )

    if not is_pqe(request.user) or not can_pqe_view_or_approve_capa(request.user, capa):
        raise PermissionDenied

    class AssignmentForm(forms.ModelForm):
        class Meta:
            model = CAPA
            fields = ["rca_role", "capa_role", "due_date"]

    form = AssignmentForm(request.POST or None, instance=capa)

    if request.method == "POST" and form.is_valid():

        updated = form.save(commit=False)

        if capa.status == "OPEN" and (updated.rca_role or updated.capa_role):
            assign_capa(capa, owner=None, actor=request.user)

        updated.save()

        return redirect("capa:capa_detail", capa_id=capa.capa_id)

    return render(request, "capa/capa_assign.html", {
        "capa": capa,
        "form": form,
    })


# =========================================================
# WORK VIEW
# =========================================================

@login_required
def capa_work_view(request, capa_id):

    capa = get_object_or_404(CAPA, capa_id=capa_id)

    user_can_rca = user_in_role_for_capa(request.user, capa, "rca_role")
    user_can_capa = user_in_role_for_capa(request.user, capa, "capa_role")

    if not (user_can_rca or user_can_capa):
        raise PermissionDenied

    if user_can_capa and not capa.rca_summary:
        user_can_capa = False

    form = CAPAUpdateForm(request.POST or None, instance=capa)

    if not user_can_rca:
        form.fields["rca_summary"].disabled = True

    if not user_can_capa:
        form.fields["capa_plan"].disabled = True

    if request.method == "POST" and form.is_valid():

        updated = form.save(commit=False)

        if not user_can_rca:
            updated.rca_summary = capa.rca_summary

        if not user_can_capa:
            updated.capa_plan = capa.capa_plan

        if user_can_rca and not updated.rca_summary.strip():
            raise PermissionDenied("RCA must be filled.")

        if user_can_capa and not updated.capa_plan.strip():
            raise PermissionDenied("CAPA plan must be filled.")

        # ================= NEW ADDITIONS =================

        # Track RCA submission (only first time)
        if user_can_rca and updated.rca_summary and not capa.rca_submitted_at:
            updated.rca_submitted_by = request.user
            updated.rca_submitted_at = timezone.now()

        # Track CAPA submission (only first time)
        if user_can_capa and updated.capa_plan and not capa.capa_submitted_at:
            updated.capa_submitted_by = request.user
            updated.capa_submitted_at = timezone.now()

        # =================================================

        updated.save()
        updated.refresh_from_db()

        if updated.is_ready_for_review and updated.status != "ACTION_DONE":
            mark_action_done(updated, request.user)

        return redirect("capa:my_assigned_capas")

    return render(request, "capa/capa_work.html", {
        "capa": capa,
        "form": form,
        "can_rca": user_can_rca,
        "can_capa": user_can_capa,
        "today": timezone.now().date(),
    })


# =========================================================
# APPROVAL PENDING
# =========================================================

@login_required
def approval_pending_capas(request):

    if not is_pqe(request.user):
        raise PermissionDenied

    capas = (
        CAPA.objects.filter(status="ACTION_DONE")
        .select_related(
            "submission",
            "submission__work_context__plant",
            "submission__work_context__line",
            "submission__work_context__shop",
            "submission__template_version__template",
            "rca_role",
            "capa_role",
        )
    )
    capas = filter_capas_for_pqe_scope(request.user, capas)

    return render(request, "capa/approval_pending_capas.html", {
        "capas": capas
    })


# =========================================================
# APPROVE
# =========================================================

@login_required
def capa_approve(request, capa_id):

    capa = get_object_or_404(
        CAPA.objects.select_related(
            "submission",
            "submission__work_context__line",
            "submission__work_context__plant",
            "submission__work_context__shop",
        ),
        capa_id=capa_id
    )

    if not is_pqe(request.user) or not can_pqe_view_or_approve_capa(request.user, capa):
        raise PermissionDenied

    close_capa(capa, request.user)

    return redirect("capa:approval_pending_capas")


# =========================================================
# REJECT
# =========================================================

@login_required
def capa_reject(request, capa_id):

    capa = get_object_or_404(
        CAPA.objects.select_related(
            "submission",
            "submission__work_context__line",
            "submission__work_context__plant",
            "submission__work_context__shop",
        ),
        capa_id=capa_id
    )

    if not is_pqe(request.user) or not can_pqe_view_or_approve_capa(request.user, capa):
        raise PermissionDenied

    reason = request.POST.get("rejection_reason")

    if not reason:
        raise PermissionDenied("Rejection reason required.")

    reject_capa(capa, request.user, reason)

    return redirect("capa:approval_pending_capas")


# =========================================================
# MY ASSIGNED CAPAS
# =========================================================

@login_required
def my_assigned_capas(request):

    user_scopes = request.user.scopes.select_related("plant", "role")

    plant_ids = user_scopes.values_list("plant_id", flat=True)
    role_ids = list(user_scopes.values_list("role_id", flat=True))

    capas = (
        CAPA.objects
        .select_related(
            "submission",
            "submission__work_context__plant",
            "submission__work_context__product",
            "submission__work_context__line",
            "submission__template_version__template",
            "rca_role",
            "capa_role",
        )
        .filter(
            submission__work_context__plant_id__in=plant_ids
        )
        .filter(
            Q(rca_role_id__in=role_ids) |
            Q(capa_role_id__in=role_ids)
        )
        .exclude(status="CLOSED")
        .order_by("due_date", "-created_at")
    )

    return render(request, "capa/my_assigned_capas.html", {
        "capas": capas,
        "user_role_ids": role_ids,
        "today": timezone.now().date(),
    })


# =========================================================
# CAPA DASHBOARD & ANALYTICS VIEWS
# =========================================================

@login_required
def capa_dashboard_view(request):
    """
    Renders the Executive & Operational CAPA Quality Dashboard
    with multi-dimensional breakdowns (Plant, Section, Brand, Line, SLA, Severity, Roles).
    """
    base_queryset = CAPA.objects.select_related(
        "submission",
        "submission__work_context__plant",
        "submission__work_context__product",
        "submission__work_context__line",
        "submission__work_context__shop",
        "submission__template_version__template",
        "rca_role",
        "capa_role",
    )

    if not request.user.is_superuser:
        plant_ids = request.user.scopes.values_list("plant_id", flat=True)
        base_queryset = base_queryset.filter(
            submission__work_context__plant_id__in=plant_ids
        )
        base_queryset = filter_capas_for_pqe_scope(request.user, base_queryset)

    # Extract query params
    selected_range = request.GET.get("range", "all")
    plant_id = request.GET.get("plant")
    shop_id = request.GET.get("shop")
    brand = request.GET.get("brand")
    line_id = request.GET.get("line")
    status = request.GET.get("status")
    severity = request.GET.get("severity")
    active_tab = request.GET.get("tab", "overview")

    plant_id = int(plant_id) if plant_id and str(plant_id).isdigit() else None
    shop_id = int(shop_id) if shop_id and str(shop_id).isdigit() else None
    line_id = int(line_id) if line_id and str(line_id).isdigit() else None
    brand = brand.strip() if brand else None
    status = status.strip() if status else None
    severity = severity.strip() if severity else None

    # Dimensional queryset (preserves plant, shop, brand, line, status, severity without date restriction)
    dimensional_qs = CapaAnalyticsService.apply_filters(
        base_queryset,
        range_key="all",
        plant_id=plant_id,
        shop_id=shop_id,
        brand=brand,
        line_id=line_id,
        status=status,
        severity=severity,
    )

    # Filter base queryset for selected range
    filtered_qs = CapaAnalyticsService.apply_filters(
        base_queryset,
        range_key=selected_range,
        plant_id=plant_id,
        shop_id=shop_id,
        brand=brand,
        line_id=line_id,
        status=status,
        severity=severity,
    )

    # Computations
    kpis = CapaAnalyticsService.compute_summary_kpis(
        filtered_qs,
        base_qs=dimensional_qs,
        range_key=selected_range,
    )
    plant_breakdown = CapaAnalyticsService.get_plant_breakdown(filtered_qs)
    section_breakdown = CapaAnalyticsService.get_section_breakdown(filtered_qs)
    brand_breakdown = CapaAnalyticsService.get_brand_breakdown(filtered_qs)
    line_breakdown = CapaAnalyticsService.get_line_breakdown(filtered_qs)
    sla_aging = CapaAnalyticsService.get_sla_aging_breakdown(
        filtered_qs,
        base_qs=dimensional_qs,
        range_key=selected_range,
    )
    severity_dist = CapaAnalyticsService.get_severity_distribution(filtered_qs)
    role_breakdown = CapaAnalyticsService.get_role_assignment_breakdown(filtered_qs)
    recent_capas = CapaAnalyticsService.get_recent_capas(filtered_qs, limit=25)
    filter_options = CapaAnalyticsService.get_filter_options()

    context = {
        "kpis": kpis,
        "plant_breakdown": plant_breakdown,
        "section_breakdown": section_breakdown,
        "brand_breakdown": brand_breakdown,
        "line_breakdown": line_breakdown,
        "sla_aging": sla_aging,
        "severity_dist": severity_dist,
        "role_breakdown": role_breakdown,
        "recent_capas": recent_capas,
        "filter_options": filter_options,
        "selected_range": selected_range,
        "selected_plant_id": plant_id,
        "selected_shop_id": shop_id,
        "selected_brand": brand,
        "selected_line_id": line_id,
        "selected_status": status,
        "selected_severity": severity,
        "active_tab": active_tab,
        "today": timezone.now().date(),
    }

    return render(request, "capa/capa_dashboard.html", context)


@login_required
def capa_dashboard_details_api(request):
    """
    JSON API for #capaDetailModal drilldown.
    Honors all current dashboard filters and returns matching CAPA records.
    """
    metric = request.GET.get("metric", "total")
    target_id = request.GET.get("target_id")
    target_name = request.GET.get("target_name")
    selected_range = request.GET.get("range") or request.GET.get("date_range") or "all"
    plant_id = request.GET.get("plant")
    shop_id = request.GET.get("shop")
    brand = request.GET.get("brand")
    line_id = request.GET.get("line")
    status = request.GET.get("status")
    severity = request.GET.get("severity")

    plant_id = int(plant_id) if plant_id and str(plant_id).isdigit() else None
    shop_id = int(shop_id) if shop_id and str(shop_id).isdigit() else None
    line_id = int(line_id) if line_id and str(line_id).isdigit() else None
    target_id = int(target_id) if target_id and str(target_id).isdigit() else None
    brand = brand.strip() if brand else None
    target_name = target_name.strip() if target_name else None
    status = status.strip() if status else None
    severity = severity.strip() if severity else None

    drill = CapaAnalyticsService.get_drilldown_details(
        metric=metric,
        target_id=target_id,
        target_name=target_name,
        plant_id=plant_id,
        shop_id=shop_id,
        brand=brand,
        line_id=line_id,
        status=status,
        severity=severity,
        range_key=selected_range,
        limit=500,
    )

    return JsonResponse({
        "success": True,
        "metric": metric,
        "target_id": target_id,
        "target_name": target_name,
        "count": drill["count"],
        "records": drill["records"],
    })

