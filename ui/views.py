# ui/views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db.models import Q
from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, time, timedelta
from ui.form_runtime.resolver import resolve_adapter
from ui.form_runtime.resolver import get_all_adapters
from core.utils.time import get_operational_window
from core.context import get_current_plant
from ui.utils.required_validation import get_missing_required_items
from core.identity.context import get_user_scope, get_user_role
from django.urls import reverse
from submissions.models import (
    WorkContext,
    Submission,
    DynamicFormSubmission,
    DynamicSubmissionApproval,
)
from submissions.services import get_required_approval_roles
from integrations.bitable.approval_status_updater import (
    update_dynamic_approval_status_async,
)
from scheduler.models import ScheduledInstance
from core.identity.models import ApprovalCategory
from org.models import Line, Product, Shop
from django.contrib import messages
from submissions.models import SubmissionApproval
from core.identity.permissions import has_permission
from core.workflow.states import WorkflowState
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden

from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from integrations.bitable.approval_status_updater import update_approval_status_async
from dynamic_forms.models import DynamicFormField


# =====================================================
# Helpers
# =====================================================

def check_permission(user, permission):
    return has_permission(user, permission)


def resolve_plant(request):
    if request.user.is_superuser:
        return None
    try:
        return get_current_plant(request)
    except RuntimeError:
        return None


def get_active_context_for_user(user):
    start, end = get_operational_window()

    context = (
        WorkContext.objects
        .filter(user=user, is_active=True)
        .select_related("plant", "line", "product")
        .first()
    )

    if context and not (start <= context.created_at < end):
        context.is_active = False
        context.save(update_fields=["is_active"])
        return None

    return context


# =====================================================
# Forms (Operator Flow)
# =====================================================

@login_required
def forms_list_view(request):
    # =====================================================
    # WORK CONTEXT (MANDATORY FOR OPERATOR MODE)
    # =====================================================
    work_context = get_active_context_for_user(request.user)

    if (
        not work_context or
        not work_context.is_active or
        not work_context.plant_id or
        not work_context.shop_id or
        not work_context.product_id
    ):
        return redirect("ui:operator_home")

    # =====================================================
    # ROLE RESOLUTION (SOFT – NO BLOCK)
    # =====================================================
    scope = get_user_scope(request.user, work_context=work_context)
    role = scope.role if scope else None
    # ❗ DO NOT raise PermissionDenied here

    # =====================================================
    # SHIFT WINDOW (08:00 → 08:00)
    # =====================================================
    now = timezone.localtime()

    start = timezone.make_aware(
        datetime.combine(now.date(), time(8, 0))
    )
    if now.time() < time(8, 0):
        start -= timedelta(days=1)

    end = start + timedelta(days=1)

    # =====================================================
    # SUBMISSIONS / KPIs
    # =====================================================
    base_qs = Submission.objects.filter(
        work_context=work_context,
        workflow_state=WorkflowState.SUBMITTED,
        submitted_at__gte=start,
        submitted_at__lt=end,
    )

    kpi_today_count = base_qs.count()
    kpi_avg_severity = (
        base_qs.aggregate(avg=models.Avg("severity_score"))["avg"] or 0
    )
    kpi_open_issues = base_qs.filter(severity_score__gte=8).count()
    kpi_last_submission = (
        base_qs.order_by("-submitted_at")
        .values_list("submitted_at", flat=True)
        .first()
    )

    # =====================================================
    # UNIFIED FORM FETCH (CHECKLIST + DYNAMIC)
    # =====================================================
    templates = []
    shift_progress_map = {}
    interval_status_map = {}

    # Pre-aggregate submission counts per template to avoid N+1 queries
    submission_counts = dict(
        base_qs
        .values("template_version__template_id")
        .annotate(cnt=models.Count("submission_id"))
        .values_list("template_version__template_id", "cnt")
    )

    for adapter in get_all_adapters():
        engine = adapter.engine_key

        adapter_templates = adapter.get_templates(
            work_context=work_context,
            user=request.user,
        )

        for t in adapter_templates:
            template_id = str(t["id"])

            # ---------------------------------------------
            # DEFENSIVE TEMPLATE FETCH
            # ---------------------------------------------
            try:
                template_obj = adapter.get_template(template_id=template_id)
            except Exception:
                continue

            # ---------------------------------------------
            # ACTIVE + PUBLISHED VERSION REQUIRED
            # ---------------------------------------------
            active_version = (
                template_obj.versions
                .filter(is_active=True, is_published=True)
                .order_by("-version_number")
                .first()
            )
            if not active_version:
                continue

            # ---------------------------------------------
            # ROLE FILTER (VISIBILITY ONLY)
            # ---------------------------------------------
            if not request.user.is_superuser:
                if not role:
                    continue  # 👈 no role → see nothing

                if engine == "CHECKLIST":
                    if not template_obj.role_assignments.filter(
                        role=role
                    ).exists():
                        continue

                elif engine == "DYNAMIC":
                    if not template_obj.role_assignments.filter(
                        role=role,
                        requires_work_context=True,
                    ).exists():
                        continue

            # ---------------------------------------------
            # BASE CARD
            # ---------------------------------------------
            card = {
                "id": template_id,
                "engine": engine,
                "name": t["name"],
                "description": t.get("description", ""),
                "active_version": active_version if engine == "CHECKLIST" else None,
                "schedule": None,
                "is_completed_for_shift": False,
            }

            # =================================================
            # CHECKLIST-SPECIFIC ENRICHMENT
            # =================================================
            if engine == "CHECKLIST":
                schedule = getattr(template_obj, "schedule", None)
                card["schedule"] = schedule

                completed_count = submission_counts.get(template_obj.id, 0)

                # ---- shift limit ----
                if schedule and schedule.schedule_type == "shift_limit":
                    required = schedule.times_per_shift or 0
                    remaining = max(required - completed_count, 0)

                    shift_progress_map[template_id] = {
                        "required": required,
                        "completed": completed_count,
                        "remaining": remaining,
                    }

                    if required > 0 and completed_count >= required:
                        card["is_completed_for_shift"] = True
                else:
                    if completed_count > 0:
                        card["is_completed_for_shift"] = True

                # ---- interval / daily ----
                if schedule and schedule.schedule_type in ("interval", "daily"):
                    if schedule.schedule_type == "interval":
                        last_instance = (
                            ScheduledInstance.objects
                            .filter(schedule=schedule)
                            .order_by("-expected_at")
                            .first()
                        )

                        interval_minutes = schedule.interval_minutes or 0
                        if interval_minutes > 0:
                            start_time = (
                                last_instance.expected_at
                                if last_instance else now
                            )

                            elapsed = max(
                                int((now - start_time).total_seconds() / 60), 0
                            )

                            percent = min(
                                int((elapsed / interval_minutes) * 100), 100
                            )

                            interval_status_map[template_id] = {
                                "type": "interval",
                                "interval_minutes": interval_minutes,
                                "elapsed_minutes": elapsed,
                                "percent": percent,
                                "is_due": elapsed >= interval_minutes,
                            }

                    elif schedule.schedule_type == "daily":
                        completed_today = ScheduledInstance.objects.filter(
                            schedule=schedule,
                            expected_at__date=now.date(),
                            is_completed=True,
                        ).exists()

                        interval_status_map[template_id] = {
                            "type": "daily",
                            "percent": 100 if completed_today else 0,
                            "is_due": not completed_today,
                        }

            # =================================================
            # DYNAMIC FORMS (SAFE DEFAULTS)
            # =================================================
            else:
                shift_progress_map[template_id] = None
                interval_status_map[template_id] = None

            templates.append(card)

    # =====================================================
    # SORT: INCOMPLETE FIRST
    # =====================================================
    templates.sort(key=lambda t: t["is_completed_for_shift"])

    # =====================================================
    # RENDER (ALWAYS ALLOWED)
    # =====================================================
    return render(
        request,
        "operator/forms_list.html",
        {
            "work_context": work_context,
            "templates": templates,
            "shift_progress_map": shift_progress_map,
            "interval_status_map": interval_status_map,

            # KPIs
            "kpi_today_count": kpi_today_count,
            "kpi_avg_severity": kpi_avg_severity,
            "kpi_open_issues": kpi_open_issues,
            "kpi_last_submission": kpi_last_submission,

            "requires_work_context": True,
        },
    )

@login_required
def unified_form_runtime_view(request, engine, template_id):

    # =====================================================
    # WORK CONTEXT (MANDATORY)
    # =====================================================
    work_context = get_active_context_for_user(request.user)
    if not work_context or not work_context.is_active:
        return redirect("ui:work_context_list")

    # =====================================================
    # RESOLVE ADAPTER
    # =====================================================
    adapter = resolve_adapter(engine)
    capabilities = adapter.get_capabilities()

    # =====================================================
    # FETCH TEMPLATE (ENGINE-SAFE)
    # =====================================================
    try:
        template = adapter.get_template(template_id=template_id)
    except Exception:
        raise Http404("Template not found")

    # =====================================================
    # ROLE RESOLUTION
    # =====================================================
    scope = get_user_scope(request.user, work_context=work_context)
    role = scope.role if scope else None

    if not request.user.is_superuser:
        if not role:
            raise PermissionDenied("No role assigned")

        # ---------------- CHECKLIST ----------------
        if engine == "CHECKLIST":
            if not template.role_assignments.filter(role=role).exists():
                raise PermissionDenied("Template not assigned to your role")

        # ---------------- DYNAMIC ----------------
        elif engine == "DYNAMIC":
            qs = template.role_assignments.filter(role=role)

            if work_context:
                qs = qs.filter(requires_work_context=True)
            else:
                qs = qs.filter(requires_work_context=False)

            if not qs.exists():
                raise PermissionDenied("Template not assigned to your role")

    # =====================================================
    # ACTIVE + PUBLISHED VERSION GUARD (🔐 CRITICAL)
    # =====================================================
    active_version = (
        template.versions
        .filter(is_active=True, is_published=True)
        .order_by("-version_number")
        .first()
    )

    if not active_version:
        raise PermissionDenied("No active published version available")

    # =====================================================
    # SUBMISSION (DRAFT)
    # =====================================================
    submission = adapter.get_or_create_draft(
        user=request.user,
        template=template,
        work_context=work_context,
    )

    # 🔒 Safety: submission MUST point to active published version
    if submission.template_version_id != active_version.id:
        submission.template_version = active_version
        submission.save(update_fields=["template_version"])

    # =====================================================
    # EDITABILITY
    # =====================================================
    is_readonly = False
    if capabilities.get("supports_partial_save"):
        if hasattr(submission, "is_editable") and not submission.is_editable():
            is_readonly = True

    # =====================================================
    # CHECKLIST STEP / SECTION
    # =====================================================
    section = None
    sections = []
    step = 1
    total_steps = 1

    if engine == "CHECKLIST":
        version = submission.template_version

        sections = list(
            version.sections
            .prefetch_related("items__rules", "items__options")
            .order_by("order")
        )

        if not sections:
            raise Http404("No sections defined")

        total_steps = len(sections)

        try:
            step = int(request.GET.get("step", 1))
        except (TypeError, ValueError):
            step = 1

        if step < 1 or step > total_steps:
            raise Http404("Invalid step")

        section = sections[step - 1]

    # =====================================================
    # POST (SAVE / SUBMIT)
    # =====================================================
    if request.method == "POST":

        adapter.save_draft(
            submission=submission,
            payload=request.POST,
            files=request.FILES,
        )

        # ---------------- REQUIRED FIELD CHECK ----------------
        missing_items = []

        if capabilities.get("supports_sections"):
            missing_items = get_missing_required_items(
                submission=submission,
                section=section,
                post_data=request.POST,
                files=request.FILES,
            )

        if missing_items:
            messages.error(
                request,
                "Please fill all required fields marked in red before continuing."
            )
            request.session["missing_item_ids"] = [
                item.id for item in missing_items
            ]
            return redirect(f"{request.path}?step={step}")

        # ---------------- NEXT STEP ----------------
        if engine == "CHECKLIST" and step < total_steps:
            return redirect(f"{request.path}?step={step + 1}")

        # ---------------- FINAL SUBMIT ----------------
        try:
            adapter.submit(
                submission=submission,
                user=request.user,
            )
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect(request.path)

        return redirect("ui:forms_list")

    # =====================================================
    # GET STATE
    # =====================================================
    missing_item_ids = request.session.pop("missing_item_ids", [])

    responses_by_item = {}
    attachments_by_item = {}

    if capabilities.get("supports_sections"):
        responses_by_item = {
            int(r.item_id): r
            for r in submission.responses.all()
            if str(r.item_id).isdigit()
        }

        # Check old SubmissionAttachment (R2 legacy)
        for att in submission.attachments.all():
            try:
                attachments_by_item.setdefault(
                    int(att.checklist_item_id), {}
                )[att.attachment_type] = att
            except (TypeError, ValueError):
                continue

        # Check new SubmissionImage (PostgreSQL binary)
        for img in submission.db_images.all():
            try:
                attachments_by_item.setdefault(
                    int(img.checklist_item_id), {}
                )[img.attachment_type] = img
            except (TypeError, ValueError):
                continue

    # =====================================================
    # DYNAMIC RUNTIME
    # =====================================================
    if engine == "DYNAMIC":

        schema = adapter.build_runtime_schema(submission=submission)
        values = adapter.get_values(submission=submission)

        return render(
            request,
            "operator/dynamic_runtime.html",
            {
                "engine": engine,
                "template": template,
                "submission": submission,
                "schema": schema,
                "values": values,
                "is_readonly": is_readonly,
                "work_context": work_context,
                "requires_work_context": True,
            },
        )

    # =====================================================
    # CHECKLIST RUNTIME
    # =====================================================
    return render(
        request,
        "operator/runtime.html",
        {
            "template": template,
            "version": submission.template_version,
            "section": section,
            "step": step,
            "total_steps": total_steps,
            "submission": submission,
            "work_context": work_context,
            "missing_item_ids": missing_item_ids,
            "responses_by_item": responses_by_item,
            "attachments_by_item": attachments_by_item,
            "requires_work_context": True,
        },
    )

@login_required
def dynamic_forms_list_view(request):
    """
    Standalone Dynamic Forms list.

    Rules:
    - NO work context
    - requires_work_context = False
    - template must have an active + published version
    - templates are FILTERED by GLOBAL role (EmployeeProfile.role)
    - page is NEVER blocked
    """

    adapter = resolve_adapter("DYNAMIC")

    templates = []
    shift_progress_map = {}
    interval_status_map = {}

    # =====================================================
    # GLOBAL ROLE RESOLUTION (STANDALONE)
    # =====================================================
    role = get_user_role(request.user, work_context=None)
    # ❗ role may be None → page still loads (empty list)

    # =====================================================
    # FETCH TEMPLATES (adapter already enforces requires_work_context=False)
    # =====================================================
    adapter_templates = adapter.get_templates(
        work_context=None,   # 🔑 STANDALONE
        user=request.user,
    )

    # =====================================================
    # VISIBILITY FILTERING
    # =====================================================
    for t in adapter_templates:
        template_id = str(t["id"])

        try:
            template = adapter.get_template(template_id=template_id)
        except Exception:
            continue

        # ---------------------------------------------
        # ACTIVE + PUBLISHED VERSION REQUIRED
        # ---------------------------------------------
        active_version = (
            template.versions
            .filter(is_active=True, is_published=True)
            .first()
        )
        if not active_version:
            continue

        # ---------------------------------------------
        # ROLE FILTER (GLOBAL ROLE)
        # ---------------------------------------------
        if not request.user.is_superuser:
            if not role:
                continue

            if not template.role_assignments.filter(
                role=role,
                requires_work_context=False,
            ).exists():
                continue

        templates.append({
            "id": template_id,
            "engine": "DYNAMIC",
            "name": t["name"],
            "description": t.get("description", ""),
            "active_version": active_version,
            "schedule": None,
            "is_completed_for_shift": False,
        })

        shift_progress_map[template_id] = None
        interval_status_map[template_id] = None

    # =====================================================
    # RENDER
    # =====================================================
    return render(
        request,
        "operator/forms_list.html",
        {
            "work_context": None,
            "requires_work_context": False,

            "templates": templates,
            "shift_progress_map": shift_progress_map,
            "interval_status_map": interval_status_map,

            # KPIs (safe defaults)
            "kpi_today_count": 0,
            "kpi_avg_severity": 0,
            "kpi_open_issues": 0,
            "kpi_last_submission": None,
        },
    )

@login_required
def dynamic_form_runtime_view(request, template_id, work_context_id=None):
    """
    Dynamic Form runtime.

    Supports:
    - Standalone mode (no work context)
    - Runtime mode (with work context)
    """

    # =====================================================
    # RESOLVE ADAPTER
    # =====================================================
    adapter = resolve_adapter("DYNAMIC")
    capabilities = adapter.get_capabilities()

    # =====================================================
    # FETCH TEMPLATE
    # =====================================================
    try:
        template = adapter.get_template(template_id=template_id)
    except Exception:
        raise Http404("Template not found")

    # =====================================================
    # RESOLVE WORK CONTEXT (OPTIONAL)
    # =====================================================
    work_context = None
    if work_context_id not in (None, "null"):
        work_context = (
            WorkContext.objects
            .filter(id=work_context_id, is_active=True)
            .select_related("plant", "shop", "product")
            .first()
        )

        if not work_context:
            raise ValidationError("Invalid or inactive Work Context")

    # =====================================================
    # ROLE RESOLUTION (CONTEXT AWARE)
    # =====================================================
    role = get_user_role(request.user, work_context=work_context)

    if not request.user.is_superuser:
        if not role:
            raise PermissionDenied("No role assigned")

        assignment = template.role_assignments.filter(
            role=role
        ).first()

        if not assignment:
            raise PermissionDenied("Template not assigned to your role")

        # Enforce work context if required
        if assignment.requires_work_context and not work_context:
            raise ValidationError(
                "Active Work Context is required for this form"
            )

    # =====================================================
    # ACTIVE + PUBLISHED VERSION GUARD
    # =====================================================
    active_version = (
        template.versions
        .filter(is_active=True, is_published=True)
        .order_by("-version_number")
        .first()
    )

    if not active_version:
        raise PermissionDenied("No active published version available")

    # =====================================================
    # SUBMISSION (CONTEXT AWARE)
    # =====================================================
    submission = adapter.get_or_create_draft(
        user=request.user,
        template=template,
        work_context=work_context,
    )

    # 🔒 Ensure submission always points to active published version
    if submission.template_version_id != active_version.id:
        submission.template_version = active_version
        submission.save(update_fields=["template_version"])

    # =====================================================
    # EDITABILITY
    # =====================================================
    is_readonly = False
    if capabilities.get("supports_partial_save"):
        if hasattr(submission, "is_editable") and not submission.is_editable():
            is_readonly = True

    # =====================================================
    # POST (SAVE / SUBMIT)
    # =====================================================
    if request.method == "POST":

        adapter.save_draft(
            submission=submission,
            payload=request.POST,
            files=request.FILES,
        )

        try:
            adapter.submit(
                submission=submission,
                user=request.user,
            )
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect(request.path)

        return redirect("ui:dynamic_forms_list")

    # =====================================================
    # GET (RUNTIME RENDER)
    # =====================================================
    schema = adapter.build_runtime_schema(submission=submission)
    values = adapter.get_values(submission=submission)

    return render(
        request,
        "operator/dynamic_runtime.html",
        {
            "engine": "DYNAMIC",
            "template": template,
            "submission": submission,
            "schema": schema,
            "values": values,
            "is_readonly": is_readonly,

            # 🔑 CONTEXT FLAGS
            "work_context": work_context,
            "requires_work_context": bool(work_context),
        },
    )
# =====================================================
# RUNTIME FORM VIEW
# =====================================================

@login_required
def form_runtime_view(request, engine, template_id):
    """
    Unified runtime view for BOTH:
    - Checklist forms
    - Dynamic forms
    """

    # =====================================================
    # WORK CONTEXT
    # =====================================================
    work_context = (
        WorkContext.objects
        .filter(user=request.user, is_active=True)
        .select_related("plant", "shop", "product")
        .first()
    )

    if not work_context:
        return redirect("ui:work_context_list")

    # =====================================================
    # RESOLVE ADAPTER
    # =====================================================
    adapter = resolve_adapter(engine)

    # =====================================================
    # TEMPLATE
    # =====================================================
    try:
        template = adapter.get_template(template_id=template_id)
    except Exception:
        raise Http404("Template not found")

    # =====================================================
    # SUBMISSION (DRAFT)
    # =====================================================
    try:
        submission = adapter.get_or_create_draft(
            user=request.user,
            template=template,
            work_context=work_context,
        )
    except Exception:
        return redirect("ui:work_context_list")

    # =====================================================
    # NON-EDITABLE STATE
    # =====================================================
    if hasattr(submission, "is_editable") and not submission.is_editable():
        return render(
            request,
            "operator/submitted.html",
            {
                "submission": submission,
                "template": template,
                "work_context": work_context,
            },
        )

    # =====================================================
    # RUNTIME SCHEMA (UNIFIED)
    # =====================================================
    schema = adapter.build_runtime_schema(submission=submission)
    sections = schema["sections"]

    total_steps = len(sections)
    supports_steps = adapter.get_capabilities().get("supports_sections", False)

    # =====================================================
    # STEP RESOLUTION
    # =====================================================
    try:
        step = int(request.GET.get("step", 1))
    except ValueError:
        step = 1

    if supports_steps:
        if step < 1 or step > total_steps:
            raise Http404("Invalid step")
        current_section = sections[step - 1]
    else:
        # Dynamic forms → single implicit section
        step = 1
        current_section = sections[0]

    # =====================================================
    # POST
    # =====================================================
    if request.method == "POST":

        # ---------------- SAVE DRAFT ----------------
        adapter.save_draft(
            submission=submission,
            payload=request.POST,
            files=request.FILES,
        )

        # ---------------- CHECKLIST REQUIRED VALIDATION ----------------
        missing_items = get_missing_required_items(
            submission=submission,
            section=current_section if supports_steps else None,
            post_data=request.POST,
            files=request.FILES,
        )

        if missing_items:
            messages.error(
                request,
                "Please fill all required fields marked in red before continuing."
            )
            request.session["missing_item_ids"] = [
                item.id for item in missing_items
            ]
            return redirect(f"{request.path}?step={step}")

        # ---------------- NEXT STEP (CHECKLIST ONLY) ----------------
        if supports_steps and step < total_steps:
            return redirect(f"{request.path}?step={step + 1}")

        # ---------------- FINAL SUBMIT ----------------
        try:
            adapter.submit(
                submission=submission,
                user=request.user,
            )
        except ValidationError as e:
            errors = e.messages if hasattr(e, "messages") else [str(e)]
            for msg in errors:
                messages.error(request, msg)
            return redirect(f"{request.path}?step={step}")

        return redirect("ui:forms_list")

    # =====================================================
    # GET STATE
    # =====================================================
    missing_item_ids = request.session.pop("missing_item_ids", [])

    context = {
        "template": template,
        "schema": schema,
        "section": current_section,
        "step": step,
        "total_steps": total_steps,
        "submission": submission,
        "work_context": work_context,
        "missing_item_ids": missing_item_ids,
        "engine": engine,
        "capabilities": adapter.get_capabilities(),
    }

    return render(
        request,
        "operator/runtime.html",
        context,
    )

# =====================================================
# Work Context
# =====================================================

@login_required
def work_context_list(request):
    start, end = get_operational_window()

    base_qs = (
        WorkContext.objects
        .filter(created_at__gte=start, created_at__lt=end)
        .select_related("user", "created_by", "plant", "shop", "line", "product")
        .order_by("-created_at")
    )

    if request.user.is_superuser or has_permission(
        request.user, "workcontext.view_all"
    ):
        contexts = base_qs
    else:
        contexts = base_qs.filter(user=request.user)

    return render(
        request,
        "work/home.html",
        {
            "contexts": contexts,
        },
    )


# =====================================================
# ROLE-BASED DASHBOARD (PERMISSION-BASED ACCESS)
# =====================================================

@login_required
def dashboard_view(request):
    """
    Modern role-based dashboard with permission-based access control
    
    Access is controlled by permissions:
    - can_view_operator_dashboard
    - can_view_supervisor_dashboard  
    - can_view_management_dashboard
    
    Superusers have access to all dashboards.
    Users are shown the highest-level dashboard they have permission to view.
    """
    from ui.dashboard_services import DashboardDataService
    
    work_context = get_active_context_for_user(request.user)
    
    # Initialize dashboard service
    dashboard_service = DashboardDataService(request.user, work_context)
    
    # Get role-appropriate data
    dashboard_data = dashboard_service.get_dashboard_data()
    
    # Check permissions (superuser gets all)
    if request.user.is_superuser:
        can_view_operator = True
        can_view_supervisor = True
        can_view_management = True
    else:
        can_view_operator = has_permission(request.user, 'can_view_operator_dashboard')
        can_view_supervisor = has_permission(request.user, 'can_view_supervisor_dashboard')
        can_view_management = has_permission(request.user, 'can_view_management_dashboard')
    
    # Add permission flags to context
    dashboard_data['can_view_operator'] = can_view_operator
    dashboard_data['can_view_supervisor'] = can_view_supervisor
    dashboard_data['can_view_management'] = can_view_management
    
    # Determine which template to use based on highest permission
    if can_view_management:
        template_name = "dashboard/management_dashboard.html"
    elif can_view_supervisor:
        template_name = "dashboard/supervisor_dashboard.html"
    else:
        # Default to operator (or if no permission, still show operator)
        template_name = "dashboard/operator_dashboard.html"
    
    return render(request, template_name, dashboard_data)


# =====================================================
# CREATE WORK CONTEXT
# =====================================================

@login_required
def work_context_create(request):

    plant = get_current_plant(request)

    # 🔒 HARD GUARD: no plant context
    if not plant:
        return redirect("ui:work_context_list")

    now = timezone.localtime()
    current_hour = now.hour
    today = now.date()
    yesterday = today - timedelta(days=1)

    # SHIFT LOGIC (unchanged)
    if 8 <= current_hour < 20:
        auto_shift = "DAY"
        production_date = today
    else:
        auto_shift = "NIGHT"
        production_date = yesterday if current_hour < 8 else today

    # Scoped Queries (Plant Safe)
    shops = Shop.objects.filter(plant=plant, is_active=True)
    lines = Line.objects.filter(shop__plant=plant, is_active=True).select_related("shop")

    products = (
        Product.objects
        .filter(
            Q(plant=plant) | Q(plant__isnull=True),
            is_active=True,
        )
        .order_by("name")
    )

    brands = (
        products
        .exclude(brand__isnull=True)
        .exclude(brand__exact="")
        .values_list("brand", flat=True)
        .distinct()
        .order_by("brand")
    )

    if request.method == "POST":

        shop_id = request.POST.get("shop")
        line_id = request.POST.get("line")
        brand = request.POST.get("brand")
        product_id = request.POST.get("product_id")

        if not all([shop_id, line_id, brand, product_id]):
            return render(
                request,
                "operator/work_create.html",
                {
                    "error": "Shop, Line, Brand and Product are mandatory",
                    "shops": shops,
                    "lines": lines,
                    "products": products,
                    "brands": brands,
                    "auto_shift": auto_shift,
                    "production_date": production_date,
                },
                status=400,
            )

        # 🔒 Validate Shop belongs to Plant
        if not Shop.objects.filter(id=shop_id, plant=plant).exists():
            return render(
                request,
                "operator/work_create.html",
                {
                    "error": "Invalid shop selection",
                    "shops": shops,
                    "lines": lines,
                    "products": products,
                    "brands": brands,
                    "auto_shift": auto_shift,
                    "production_date": production_date,
                },
                status=400,
            )

        # 🔒 Validate Line belongs to Shop + Plant
        if not Line.objects.filter(
            id=line_id,
            shop_id=shop_id,
            shop__plant=plant
        ).exists():
            return render(
                request,
                "operator/work_create.html",
                {
                    "error": "Selected line does not belong to selected shop",
                    "shops": shops,
                    "lines": lines,
                    "products": products,
                    "brands": brands,
                    "auto_shift": auto_shift,
                    "production_date": production_date,
                },
                status=400,
            )

        # 🔒 Validate Product belongs to Brand + Plant Scope
        if not Product.objects.filter(
            id=product_id,
            brand=brand,
        ).filter(
            Q(plant=plant) | Q(plant__isnull=True)
        ).exists():
            return render(
                request,
                "operator/work_create.html",
                {
                    "error": "Selected product does not belong to selected brand",
                    "shops": shops,
                    "lines": lines,
                    "products": products,
                    "brands": brands,
                    "auto_shift": auto_shift,
                    "production_date": production_date,
                },
                status=400,
            )

        WorkContext.objects.create(
            user=request.user,
            created_by=request.user,
            plant=plant,
            shop_id=shop_id,
            line_id=line_id,
            product_id=product_id,
            model_color=request.POST.get("model_color", ""),
            shift=auto_shift,
            work_date=production_date,
            process_type=request.POST.get("process_type", "IPQC"),
            is_active=False,
        )

        return redirect("ui:work_context_list")

    return render(
        request,
        "operator/work_create.html",
        {
            "shops": shops,
            "lines": lines,
            "products": products,
            "brands": brands,
            "auto_shift": auto_shift,
            "production_date": production_date,
        },
    )
    
# =====================================================
# ACTIVATE WORK CONTEXT
# =====================================================

@login_required
@transaction.atomic
def work_context_activate(request, context_id):

    context = get_object_or_404(
        WorkContext,
        id=context_id,
        user=request.user,
    )

    # 🔒 Extra safety (plant consistency)
    current_plant = context.plant
    if not current_plant:
        return redirect("ui:work_context_list")

    # 🔥 SINGLE SOURCE OF TRUTH (atomic)
    WorkContext.objects.filter(
        user=request.user,
        plant=current_plant,
        is_active=True,
    ).exclude(id=context.id).update(is_active=False)

    context.is_active = True
    context.save(update_fields=["is_active"])

    return redirect("ui:forms_list")


# =====================================================
# OPERATOR HOME
# =====================================================

@login_required
def operator_home(request):

    start, end = get_operational_window()
    today = start.date()

    active_context = (
        WorkContext.objects
        .filter(
            user=request.user,
            work_date=today,
            is_active=True
        )
        .select_related("plant", "line", "product")
        .first()
    )

    inactive_contexts = (
        WorkContext.objects
        .filter(
            user=request.user,
            work_date=today,
            is_active=False
        )
        .select_related("plant", "line", "product")
        .order_by("-created_at")
    )

    return render(
        request,
        "operator/home.html",
        {
            "active_context": active_context,
            "today_context": inactive_contexts.first(),
            "inactive_contexts": inactive_contexts,
            "inactive_count": inactive_contexts.count(),
            "window_start": start,
            "window_end": end,
        },
    )


# =====================================================
# NOTIFICATIONS
# =====================================================

@login_required
def notification_list_view(request):
    """
    Display user's missed form alerts and reminders
    """
    from scheduler.models import MissedFormAlert
    
    # Get all alerts for the current user
    alerts = MissedFormAlert.objects.filter(
        user=request.user
    ).select_related(
        'template',
        'instance__schedule'
    ).order_by('-created_at')
    
    # Split into missed forms and upcoming reminders
    missed_forms = []
    upcoming_reminders = []
    
    now = timezone.now()
    
    for alert in alerts:
        # If notification_sent is True, it's a reminder (upcoming)
        # If notification_sent is False, it's a missed form alert
        if alert.notification_sent and alert.expected_at > now:
            upcoming_reminders.append(alert)
        else:
            missed_forms.append(alert)
    
    return render(
        request,
        "operator/notification_list.html",
        {
            "missed_forms": missed_forms,
            "upcoming_reminders": upcoming_reminders,
            "total_count": len(missed_forms) + len(upcoming_reminders),
        },
    )


# =====================================================
# MAIN HOME
# =====================================================

@login_required
def main_home(request):

    user = request.user

    context = {
        # ===== QUALITY PERMISSIONS =====
        "can_fill_forms": has_permission(user, "can_fill_forms"),
        "can_view_analytics": has_permission(user, "can_view_analytics"),
        "can_manage_capa": has_permission(user, "can_manage_capa"),
        "can_approve_ipqc": has_permission(user, "can_approve_ipqc"),

        # ===== EHS PERMISSIONS =====
        "can_fill_ehs_forms": has_permission(user, "can_fill_ehs_forms"),
        "can_manage_ehs_templates": has_permission(user, "can_manage_ehs_templates"),
        "can_view_ehs_reports": has_permission(user, "can_view_ehs_reports"),
        "can_approve_ehs": has_permission(user, "can_approve_ehs"),
    }

    return render(request, "shell/main_home.html", context)




from datetime import datetime, timedelta, time
from django.utils import timezone


def _resolve_date_range(now, selected_range):
    PRODUCTION_TIME = time(8, 0)

    # Always work with aware datetime
    now = timezone.localtime(now)

    def at_8am(d):
        return timezone.make_aware(datetime.combine(d, PRODUCTION_TIME))

    today = now.date()
    today_8am = at_8am(today)

    # -------------------------------
    # TODAY (08:00 → next day 08:00)
    # -------------------------------
    if selected_range == "today":
        if now < today_8am:
            start = at_8am(today - timedelta(days=1))
            end = today_8am
        else:
            start = today_8am
            end = at_8am(today + timedelta(days=1))
        return start, end

    # -------------------------------
    # THIS WEEK (Mon 08:00 → Next Mon 08:00)
    # -------------------------------
    if selected_range == "this_week":
        monday = today - timedelta(days=today.weekday())  # Monday
        start = at_8am(monday)
        end = start + timedelta(days=7)
        return start, end

    # -------------------------------
    # LAST WEEK (Previous Mon 08:00 → Mon 08:00)
    # -------------------------------
    if selected_range == "last_week":
        last_monday = today - timedelta(days=today.weekday() + 7)
        start = at_8am(last_monday)
        end = start + timedelta(days=7)
        return start, end

    # -------------------------------
    # THIS MONTH (1st 08:00 → 1st of next month 08:00)
    # -------------------------------
    if selected_range == "this_month":
        first_day = today.replace(day=1)
        start = at_8am(first_day)

        if first_day.month == 12:
            next_month = first_day.replace(year=first_day.year + 1, month=1)
        else:
            next_month = first_day.replace(month=first_day.month + 1)

        end = at_8am(next_month)
        return start, end

    # -------------------------------
    # DEFAULT (safe fallback)
    # -------------------------------
    return today_8am, today_8am + timedelta(days=1)

# =====================================================
# Submission / CAPA
# =====================================================

@login_required
def submission_detail_view(request, submission_id):
    """
    Unified submission detail view
    - Checklist + Dynamic
    - Read-only
    - Department-based access enforced (NEW)
    """

    user = request.user

    # ----------------------------------
    # Detect submission type
    # ----------------------------------
    try:
        submission = (
            Submission.objects
            .select_related(
                "template_version__template",
                "work_context__plant",
                "work_context__line",
                "work_context__product",
                "submitted_by",
            )
            .prefetch_related("approvals__category", "attachments")
            .get(submission_id=submission_id)
        )
        engine = "CHECKLIST"

    except Submission.DoesNotExist:
        submission = (
            DynamicFormSubmission.objects
            .select_related(
                "template_version__template",
                "submitted_by",
            )
            .prefetch_related("approvals__category", "values__field")
            .get(submission_id=submission_id)
        )
        engine = "DYNAMIC"

    # ----------------------------------
    # 🔐 DEPARTMENT ACCESS (NEW – SAFE)
    # ----------------------------------
    if not user.is_superuser:
        user_departments = set(
            user.scopes
            .exclude(department__isnull=True)
            .values_list("department_id", flat=True)
        )

        template_department_id = (
            submission.template_version.template.department_id
        )

        # If user has no department scope OR template not in scope → deny
        if not user_departments or template_department_id not in user_departments:
            raise PermissionDenied

    # ----------------------------------
    # 🔐 ACCESS CONTROL (UNCHANGED)
    # ----------------------------------
    if not user.is_superuser:
        if submission.submitted_by != user and not (
            has_permission(user, "can_view_submissions")
            or has_permission(user, "workcontext.view_all")
        ):
            raise PermissionDenied

    # ----------------------------------
    # CHECKLIST CONTEXT
    # ----------------------------------
    if engine == "CHECKLIST":
        sections = (
            submission.template_version.sections
            .prefetch_related("items")
            .order_by("order")
        )

        responses_qs = submission.responses.all()
        answers = {str(r.item_id): r.value for r in responses_qs}
        responses = {str(r.item_id): r for r in responses_qs}

        # Build unified attachments map (old + new)
        attachments_by_item = {}
        for att in submission.attachments.all():
            try:
                attachments_by_item.setdefault(
                    int(att.checklist_item_id), {}
                )[att.attachment_type] = att
            except (TypeError, ValueError):
                continue
        for img in submission.db_images.all():
            try:
                attachments_by_item.setdefault(
                    int(img.checklist_item_id), {}
                )[img.attachment_type] = img
            except (TypeError, ValueError):
                continue

        return render(
            request,
            "operator/submission_detail.html",
            {
                "engine": engine,
                "submission": submission,
                "sections": sections,
                "answers": answers,
                "responses": responses,
                "attachments_by_item": attachments_by_item,
                "approval": submission.approvals.order_by("created_at").last(),
            },
        )

    # ----------------------------------
    # DYNAMIC CONTEXT
    # ----------------------------------
    values_qs = submission.values.select_related("field")

    answers = {
        str(v.field_id): v.value
        for v in values_qs
    }

    responses = {
        str(v.field_id): v
        for v in values_qs
    }

    fields = (
        submission.template_version.fields
        .all()
        .order_by("order")
    )

    approvals = submission.approvals.order_by("created_at")

    return render(
        request,
        "operator/submission_detail_dynamic.html",
        {
            "submission": submission,
            "fields": fields,
            "answers": answers,
            "responses": responses,
            "approvals": approvals,
        },
    )

@login_required
def submission_list_view(request):
    """
    Unified submission list
    - Checklist + Dynamic
    - Date range filters (same as IPQC dashboard)
    - Access control preserved
    - Department-based visibility (NEW)
    """

    user = request.user
    selected_range = request.GET.get("range", "today")

    now = timezone.localtime()
    start_date, end_date = _resolve_date_range(now, selected_range)

    # ----------------------------------
    # BASE QUERYSETS (DATE FILTERED)
    # ----------------------------------
    checklist_qs = (
        Submission.objects
        .filter(
            submitted_at__gte=start_date,
            submitted_at__lt=end_date,
        )
        .select_related(
            "template_version__template",
            "submitted_by",
            "line",
            "product",
        )
        .prefetch_related(
            "approvals__category",
            "submitted_by__scopes__role",
            "submitted_by__employee_profile__role",
        )
        .order_by("-submitted_at")
    )

    dynamic_qs = (
        DynamicFormSubmission.objects
        .filter(
            submitted_at__gte=start_date,
            submitted_at__lt=end_date,
        )
        .select_related(
            "template_version__template",
            "submitted_by",
        )
        .prefetch_related(
            "approvals__category",
            "submitted_by__scopes__role",
            "submitted_by__employee_profile__role",
        )
        .order_by("-submitted_at")
    )

    # ----------------------------------
    # DEPARTMENT FILTER (NEW – SAFE)
    # ----------------------------------
    if not user.is_superuser:
        user_departments = set(
            user.scopes
            .exclude(department__isnull=True)
            .values_list("department_id", flat=True)
        )

        if user_departments:
            checklist_qs = checklist_qs.filter(
                template_version__template__department_id__in=user_departments
            )
            dynamic_qs = dynamic_qs.filter(
                template_version__template__department_id__in=user_departments
            )
        else:
            # No department scope → see nothing
            checklist_qs = checklist_qs.none()
            dynamic_qs = dynamic_qs.none()

    # ----------------------------------
    # ACCESS CONTROL (UNCHANGED – AS REQUESTED)
    # ----------------------------------
    if not user.is_superuser:
        if not (
            has_permission(user, "can_view_submissions")
            or has_permission(user, "workcontext.view_all")
        ):
            checklist_qs = checklist_qs.filter(submitted_by=user)
            dynamic_qs = dynamic_qs.filter(submitted_by=user)

    submissions = []

    # ----------------------------------
    # HELPERS (IN-MEMORY OPTIMIZED)
    # ----------------------------------
    def resolve_submitter_role(u):
        scopes = list(u.scopes.all())
        if scopes and scopes[0].role:
            return scopes[0].role.name
        if hasattr(u, "employee_profile") and u.employee_profile and u.employee_profile.role:
            return u.employee_profile.role.name
        return "-"

    def resolve_approval_status(obj):
        approvals = list(obj.approvals.all())
        if not approvals:
            return "NO_APPROVAL"
        approvals.sort(key=lambda a: (a.category.order if a.category and hasattr(a.category, 'order') else 0, a.created_at or timezone.now()))
        return approvals[-1].status

    # ----------------------------------
    # CHECKLIST → UNIFIED SHAPE
    # ----------------------------------
    for s in checklist_qs:
        submissions.append({
            "id": s.submission_id,
            "template_name": s.template_version.template.name,
            "submitted_at": s.submitted_at,
            "submitter_name": (
                s.submitted_by.get_full_name()
                or s.submitted_by.username
            ),
            "submitter_role": resolve_submitter_role(s.submitted_by),
            "line_name": s.line.name if s.line else None,
            "product_name": s.product.name if s.product else None,
            "approval_status": resolve_approval_status(s),
        })

    # ----------------------------------
    # DYNAMIC → UNIFIED SHAPE
    # ----------------------------------
    for s in dynamic_qs:
        submissions.append({
            "id": s.submission_id,
            "template_name": s.template_version.template.name,
            "submitted_at": s.submitted_at,
            "submitter_name": (
                s.submitted_by.get_full_name()
                or s.submitted_by.username
            ),
            "submitter_role": resolve_submitter_role(s.submitted_by),
            "line_name": None,
            "product_name": None,
            "approval_status": resolve_approval_status(s),
        })

    # ----------------------------------
    # SORT (GLOBAL)
    # ----------------------------------
    submissions.sort(
        key=lambda x: x["submitted_at"] or timezone.now(),
        reverse=True,
    )

    return render(
        request,
        "operator/submission_list.html",
        {
            "submissions": submissions,
            "selected_range": selected_range,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    
    

@login_required
def ipqc_dashboard_view(request):
    """
    Unified IPQC dashboard
    - Checklist + Dynamic
    - Logged-in user's submissions ONLY
    - Date-range filter aware
    """

    user = request.user
    selected_range = request.GET.get("range", "today")
    page_number = request.GET.get("page", 1)
    per_page = int(request.GET.get("per_page", 12))

    now = timezone.localtime()
    start_date, end_date = _resolve_date_range(now, selected_range)

    # -------------------------------------------------
    # CHECKLIST SUBMISSIONS
    # -------------------------------------------------
    checklist_qs = (
        Submission.objects
        .filter(
            submitted_by=user,
            workflow_state__in=[
                WorkflowState.SUBMITTED,
                WorkflowState.CLOSED,
                WorkflowState.FAILED,
            ],
            submitted_at__gte=start_date,
            submitted_at__lt=end_date,
        )
        .select_related(
            "template_version__template",
            "submitted_by",
            "line",
            "product",
        )
        .prefetch_related("approvals__category")
    )

    # -------------------------------------------------
    # DYNAMIC SUBMISSIONS
    # -------------------------------------------------
    dynamic_qs = (
        DynamicFormSubmission.objects
        .filter(
            submitted_by=user,
            workflow_state__in=[
                WorkflowState.SUBMITTED,
                WorkflowState.CLOSED,
                WorkflowState.FAILED,
            ],
            submitted_at__gte=start_date,
            submitted_at__lt=end_date,
        )
        .select_related(
            "template_version__template",
            "submitted_by",
        )
        .prefetch_related("approvals__category")
    )

    # -------------------------------------------------
    # UNIFY DATA
    # -------------------------------------------------
    submissions = []

    def resolve_pqe_status(obj):
        pqes = [a for a in obj.approvals.all() if a.category and a.category.code == "PQE"]
        if not pqes:
            return "PENDING"
        pqes.sort(key=lambda a: a.created_at or timezone.now())
        return pqes[-1].status

    for s in checklist_qs:
        submissions.append({
            "id": s.submission_id,
            "engine": "CHECKLIST",
            "template_name": s.template_version.template.name,
            "submitted_at": s.submitted_at,
            "workflow_state": s.workflow_state,
            "severity": s.severity_score,
            "line": s.line.name if s.line else None,
            "product": s.product.name if s.product else None,
            "approval_status": resolve_pqe_status(s),
        })

    for s in dynamic_qs:
        submissions.append({
            "id": s.submission_id,
            "engine": "DYNAMIC",
            "template_name": s.template_version.template.name,
            "submitted_at": s.submitted_at,
            "workflow_state": s.workflow_state,
            "severity": None,
            "line": None,
            "product": None,
            "approval_status": resolve_pqe_status(s),
        })

    # -------------------------------------------------
    # SORT + PAGINATE
    # -------------------------------------------------
    submissions.sort(
        key=lambda x: x["submitted_at"] or timezone.now(),
        reverse=True,
    )

    paginator = Paginator(submissions, per_page)
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "operator/ipqc_dashboard.html",
        {
            "page_obj": page_obj,
            "selected_range": selected_range,
            "per_page": per_page,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    
    

@login_required
def capa_list_view(request):

    if not check_permission(request.user, "can_manage_capa"):
        raise PermissionDenied

    from capa.models import CAPA

    qs = CAPA.objects.select_related("submission", "submission__plant")

    if not request.user.is_superuser:
        qs = qs.filter(submission__plant__isnull=False)

    return render(request, "capa/capa_list.html", {"capas": qs})


@login_required
def capa_detail_view(request, capa_id):

    if not check_permission(request.user, "can_manage_capa"):
        raise PermissionDenied

    from capa.models import CAPA

    capa = get_object_or_404(
        CAPA.objects.select_related("submission", "submission__plant"),
        capa_id=capa_id
    )

    return render(request, "capa/capa_detail.html", {"capa": capa})



@login_required
def submission_detail_popup(request, submission_id):

    submission = get_object_or_404(
        Submission.objects.select_related(
            "template_version__template",
            "work_context__plant",
            "work_context__line",
            "work_context__product",
        ).prefetch_related(
            "approvals__category"   # 🔑 important for category lookup
        ),
        submission_id=submission_id,
    )

    sections = (
        submission.template_version.sections
        .prefetch_related("items")
        .order_by("order")
    )

    responses_qs = submission.responses.all()

    answers = {str(r.item_id): r.value for r in responses_qs}
    responses = {str(r.item_id): r for r in responses_qs}

    # --------------------------------------------------
    # ✅ CATEGORY-BASED APPROVAL (PQE)
    # --------------------------------------------------
    approval = submission.approvals.filter(
        category__code="PQE"
    ).first()

    return render(
        request,
        "operator/submission_popup.html",
        {
            "submission": submission,
            "sections": sections,
            "answers": answers,
            "responses": responses,
            "approval": approval,
        },
    )


@login_required
def dynamic_submission_detail_popup(request, submission_id):
    """
    Internal popup view for DYNAMIC FORM submissions (approval dashboard)
    """

    submission = get_object_or_404(
        DynamicFormSubmission.objects.select_for_update(of=("self",)).select_related(
            "template_version__template",
            "work_context__plant",
            "submitted_by",
        ).prefetch_related(
            "values__field",
            "approvals__category",
        ),
        submission_id=submission_id,
    )

    template = submission.template_version.template
    flow = get_required_approval_flow(template)
    approved = get_approved_categories(submission)
    current_category_code = get_current_approval_category(template, submission)

    can_approve = False
    approval_category = None
    if current_category_code and submission.workflow_state == WorkflowState.SUBMITTED:
        try:
            approval_category = ApprovalCategory.objects.get(
                code=current_category_code,
                is_active=True,
                is_approver=True,
            )
            can_approve = is_user_authorized_for_category(request.user, template, current_category_code)
        except ApprovalCategory.DoesNotExist:
            pass

    full_name = request.user.get_full_name() or request.user.username
    default_approver_name = f"{request.user.username} {full_name}".strip()

    if request.method == "POST":
        if not can_approve or not current_category_code or not approval_category:
            return JsonResponse({"success": False, "error": "Not authorized or no pending approval for this step"}, status=403)

        status = request.POST.get("status")
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        approver_name = request.POST.get("approver_name", "").strip() or default_approver_name

        if status not in ("APPROVED", "REJECTED"):
            return JsonResponse({"success": False, "error": "Invalid status"}, status=400)

        if status == "REJECTED" and not rejection_reason:
            return JsonResponse({"success": False, "error": "Rejection reason required"}, status=400)

        approval = DynamicSubmissionApproval.objects.create(
            submission=submission,
            category=approval_category,
            status=status,
            approver_name=approver_name,
            rejection_reason=rejection_reason,
        )

        if status == "REJECTED":
            submission.workflow_state = WorkflowState.FAILED
        else:
            approved.add(approval_category.code)
            if set(flow).issubset(approved):
                submission.workflow_state = WorkflowState.CLOSED

        submission.save(update_fields=["workflow_state"])
        update_dynamic_approval_status_async(submission, approval)

        return JsonResponse({
            "success": True,
            "submission_id": str(submission.submission_id),
            "status": status,
        })

    # Fields (ordered)
    fields = (
        DynamicFormField.objects
        .filter(version=submission.template_version)
        .order_by("order")
    )

    # Values
    values_qs = submission.values.select_related("field")

    answers = {str(v.field_id): v.value for v in values_qs}
    responses = {str(v.field_id): v for v in values_qs}

    approvals = submission.approvals.all()

    return render(
        request,
        "public/dynamic_submission_popup.html",
        {
            "submission": submission,
            "fields": fields,
            "answers": answers,
            "responses": responses,
            "approvals": approvals,
            "can_approve": can_approve,
            "current_category_code": current_category_code,
            "default_approver_name": default_approver_name,
        },
    )

@login_required
@transaction.atomic
def pqe_review_and_approve(request, submission_id):

    submission = get_object_or_404(
        Submission.objects.select_for_update(of=("self",)).select_related(
            "work_context",
            "plant",
            "line",
            "product",
            "template_version__template",
        ).prefetch_related(
            "approvals__category"
        ),
        submission_id=submission_id,
        workflow_state=WorkflowState.SUBMITTED,
    )

    template = submission.template_version.template

    # --------------------------------------------------
    # RESOLVE CURRENT APPROVAL CATEGORY FROM TEMPLATE FLOW
    # --------------------------------------------------
    flow = get_required_approval_flow(template)
    approved = get_approved_categories(submission)
    current_category_code = get_current_approval_category(template, submission)

    if current_category_code is None:
        return HttpResponse("Already fully approved", status=400)

    try:
        approval_category = ApprovalCategory.objects.get(
            code=current_category_code,
            is_active=True,
            is_approver=True,
        )
    except ApprovalCategory.DoesNotExist:
        return HttpResponseBadRequest(
            f"{current_category_code} approval category not configured"
        )

    # --------------------------------------------------
    # ROLE VERIFICATION (INCLUDE TEMPLATE ROLE ASSIGNMENTS)
    # --------------------------------------------------
    if not is_user_authorized_for_category(request.user, template, current_category_code):
        return HttpResponseForbidden("Not allowed to approve this category")

    # --------------------------------------------------
    # ALREADY APPROVED?
    # --------------------------------------------------
    if submission.approvals.filter(category=approval_category).exists():
        return HttpResponse("Already approved", status=400)

    # --------------------------------------------------
    # AUTO-FILL APPROVER NAME: user id + name
    # --------------------------------------------------
    full_name = request.user.get_full_name() or request.user.username
    default_approver_name = f"{request.user.username} {full_name}".strip()

    # --------------------------------------------------
    # HANDLE POST
    # --------------------------------------------------
    if request.method == "POST":

        status = request.POST.get("status")
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        approver_name = request.POST.get("approver_name", "").strip() or default_approver_name

        if status not in ("APPROVED", "REJECTED"):
            return HttpResponseBadRequest("Invalid status")

        if status == "REJECTED" and not rejection_reason:
            return JsonResponse(
                {"success": False, "error": "Rejection reason required"},
                status=400,
            )

        approval = SubmissionApproval.objects.create(
            submission=submission,
            category=approval_category,
            status=status,
            approver_name=approver_name,
            rejection_reason=rejection_reason,
        )

        # --------------------------------------------------
        # WORKFLOW TRANSITION
        # --------------------------------------------------
        if status == "REJECTED":
            submission.workflow_state = WorkflowState.FAILED
        else:
            # If all required categories approved, close
            approved.add(approval_category.code)
            if set(flow).issubset(approved):
                submission.workflow_state = WorkflowState.CLOSED

        submission.save(update_fields=["workflow_state"])

        # --------------------------------------------------
        # BITABLE UPDATE
        # --------------------------------------------------
        update_approval_status_async(
            submission=submission,
            approval=approval,
        )

        return JsonResponse({
            "success": True,
            "submission_id": str(submission.submission_id),
            "status": status,
            "rejection_reason": rejection_reason,
        })

    # --------------------------------------------------
    # GET: RENDER APPROVAL SCREEN
    # --------------------------------------------------
    sections = (
        submission.template_version.sections
        .prefetch_related("items")
        .order_by("order")
    )

    responses_qs = submission.responses.all()
    answers = {str(r.item_id): r.value for r in responses_qs}
    responses = {str(r.item_id): r for r in responses_qs}

    return render(
        request,
        "approval/approval_popup.html",
        {
            "submission": submission,
            "sections": sections,
            "answers": answers,
            "responses": responses,
            "approval_category": approval_category,
            "default_approver_name": default_approver_name,
            "current_category_code": current_category_code,
            "can_approve": True,
        },
    )


def get_required_approval_flow(template):
    if not template:
        return []

    if hasattr(template, "approval_steps"):
        steps = list(
            template.approval_steps
            .filter(is_required=True)
            .select_related("category")
            .order_by("order")
            .values_list("category__code", flat=True)
        )
        if steps:
            return steps

    flow_str = getattr(template, "approval_flow", "") or ""
    flow_str = str(flow_str).strip()
    if flow_str and flow_str.upper() != "NONE":
        parts = [p.strip().upper() for p in flow_str.split("_") if p.strip()]
        valid_parts = [p for p in parts if p != "NONE"]
        if valid_parts:
            return valid_parts

    return []


def get_user_auth_permissions(user):
    if not user or not user.is_authenticated or user.is_superuser:
        return set(), set()
    user_categories = set(
        ApprovalCategory.objects.filter(
            is_active=True,
            is_approver=True,
            roles__user_scopes__user=user,
        ).values_list("code", flat=True)
    )
    user_categories.update(
        ApprovalCategory.objects.filter(
            is_active=True,
            is_approver=True,
            roles__employee_profiles__user=user,
        ).values_list("code", flat=True)
    )
    user_role_codes = set(user.scopes.values_list("role__code", flat=True))
    user_role_codes.update(user.scopes.values_list("role__name", flat=True))
    if hasattr(user, "employee_profile") and user.employee_profile and user.employee_profile.role:
        user_role_codes.add(user.employee_profile.role.code)
        user_role_codes.add(user.employee_profile.role.name)

    return {c.upper() for c in user_categories if c}, {c.upper() for c in user_role_codes if c}


def is_user_authorized_for_category(user, template, category_code, cached_user_perms=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    category_code_upper = category_code.upper() if category_code else ""

    if cached_user_perms is not None:
        user_categories_upper, user_role_codes_upper = cached_user_perms
    else:
        user_categories_upper, user_role_codes_upper = get_user_auth_permissions(user)

    if category_code_upper in user_categories_upper:
        return True

    if category_code_upper in user_role_codes_upper:
        return True

    # 3) TemplateRole assignments (only for ChecklistTemplate)
    from forms_engine.models import ChecklistTemplate
    if template and isinstance(template, ChecklistTemplate):
        from forms_engine.models import TemplateRole
        is_template_role_user = TemplateRole.objects.filter(
            template=template,
            role__user_scopes__user=user,
        ).exists() or TemplateRole.objects.filter(
            template=template,
            role__employee_profiles__user=user,
        ).exists()
        if is_template_role_user:
            return True

    return False


def get_approved_categories(submission):
    if hasattr(submission, "_prefetched_objects_cache") and "approvals" in submission._prefetched_objects_cache:
        return {
            a.category.code for a in submission.approvals.all()
            if a.status == "APPROVED" and a.category
        }
    return set(
        submission.approvals
        .filter(status="APPROVED")
        .values_list("category__code", flat=True)
    )


def get_current_approval_category(template, submission):
    flow = get_required_approval_flow(template)
    approved = get_approved_categories(submission)

    for code in flow:
        if code not in approved:
            return code

    return None


@login_required
def approval_pending_dashboard(request):
    """
    Unified approval dashboard:
    - Checklist + Dynamic
    - Shows ONLY submissions with pending approval
    - Inactive order cards are faded
    """

    user = request.user
    cards = []
    cached_user_perms = get_user_auth_permissions(user)

    # =======================================
    # CHECKLIST SUBMISSIONS
    # =======================================
    checklist_qs = (
        Submission.objects
        .filter(workflow_state=WorkflowState.SUBMITTED)
        .select_related(
            "template_version__template",
            "submitted_by",
            "line",
            "product",
        )
        .prefetch_related(
            "approvals__category",
            "template_version__template__approval_steps__category",
        )
    )

    for submission in checklist_qs:
        template = submission.template_version.template

        flow = get_required_approval_flow(template)
        if not flow:
            continue  # 🔒 no approval flow → ignore

        approved = get_approved_categories(submission)
        current = get_current_approval_category(template, submission)

        if current is None:
            continue

        can_approve = is_user_authorized_for_category(user, template, current, cached_user_perms=cached_user_perms)

        cards.append({
            "engine": "CHECKLIST",
            "submission": submission,
            "template_name": template.name,
            "submitted_at": submission.submitted_at,
            "submitted_by": submission.submitted_by,
            "line": submission.line,
            "product": submission.product,

            "approval_flow": flow,
            "approved": approved,
            "current": current,

            "can_approve": can_approve,
        })

    # =======================================
    # DYNAMIC SUBMISSIONS
    # =======================================
    dynamic_qs = (
        DynamicFormSubmission.objects
        .filter(workflow_state=WorkflowState.SUBMITTED)
        .select_related(
            "template_version__template",
            "submitted_by",
        )
        .prefetch_related(
            "approvals__category",
            "template_version__template__approval_steps__category",
        )
    )

    for submission in dynamic_qs:
        template = submission.template_version.template

        flow = get_required_approval_flow(template)

        if not flow:
            continue

        approved = get_approved_categories(submission)

        current = get_current_approval_category(template, submission)

        if current is None:
            continue

        can_approve = is_user_authorized_for_category(user, template, current, cached_user_perms=cached_user_perms)

        cards.append({
            "engine": "DYNAMIC",
            "submission": submission,
            "template_name": template.name,
            "submitted_at": submission.submitted_at,
            "submitted_by": submission.submitted_by,

            "approval_flow": flow,
            "approved": approved,
            "current": current,

            "can_approve": can_approve,
        })

    # ---------------------------------------
    # SORT: actionable first
    # ---------------------------------------
    cards.sort(key=lambda c: not c["can_approve"])

    return render(
        request,
        "approval/pending_dashboard.html",
        {
            "cards": cards,
        },
    )
    
    
@login_required
@transaction.atomic
def approve_submission(request, submission_id):
    """
    Unified approval endpoint

    - Works for CHECKLIST and DYNAMIC submissions
    - Enforces role + approval order
    - Resolves plant correctly (submission / work_context / template)
    - Updates correct Bitable table
    """

    # --------------------------------------------------
    # METHOD CHECK
    # --------------------------------------------------
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Invalid request method"},
            status=405,
        )

    # --------------------------------------------------
    # CATEGORY
    # --------------------------------------------------
    category_code = request.POST.get("category")
    if not category_code:
        return JsonResponse(
            {"success": False, "message": "Missing approval category"},
            status=400,
        )

    category = get_object_or_404(
        ApprovalCategory,
        code=category_code,
        is_active=True,
        is_approver=True,
    )

    # --------------------------------------------------
    # DETECT SUBMISSION TYPE
    # --------------------------------------------------
    submission = None
    engine = None

    try:
        # ---------- CHECKLIST ----------
        submission = (
            Submission.objects
            .select_for_update(of=("self",))
            .select_related(
                "plant",
                "template_version__template",
            )
            .prefetch_related("approvals")
            .get(
                submission_id=submission_id,
                workflow_state=WorkflowState.SUBMITTED,
            )
        )
        engine = "CHECKLIST"

    except Submission.DoesNotExist:
        # ---------- DYNAMIC ----------
        submission = (
            DynamicFormSubmission.objects
            .select_for_update(of=("self",))
            .select_related(
                "template_version__template",
                "work_context__plant",
            )
            .prefetch_related("approvals")
            .get(
                submission_id=submission_id,
                workflow_state=WorkflowState.SUBMITTED,
            )
        )
        engine = "DYNAMIC"

    # --------------------------------------------------
    # 🔑 RESOLVE PLANT(S) — NO Plant MODEL NEEDED
    # --------------------------------------------------
    if engine == "CHECKLIST":
        # submission.plant is a FK → use its ID
        plant_ids = [submission.plant_id] if submission.plant_id else []

    else:
        # Dynamic
        if submission.work_context and submission.work_context.plant_id:
            plant_ids = [submission.work_context.plant_id]
        else:
            # Template-scoped plants (M2M)
            plant_ids = list(
                submission.template_version.template.plants
                .values_list("id", flat=True)
            )

    if not plant_ids:
        return JsonResponse(
            {
                "success": False,
                "message": "No plant context resolved for this submission",
            },
            status=400,
        )

    # --------------------------------------------------
    # TEMPLATE (Used by role authorization + approval flow)
    # --------------------------------------------------
    template = submission.template_version.template

    # --------------------------------------------------
    # 🔐 ROLE AUTHORIZATION
    # --------------------------------------------------
    if not is_user_authorized_for_category(request.user, template, category.code):
        return JsonResponse(
            {
                "success": False,
                "error_type": "ROLE_BLOCKED",
                "message": f"You are not authorized to approve {category.code}",
            },
            status=403,
        )

    # --------------------------------------------------
    # APPROVAL FLOW (ENGINE AWARE)
    # --------------------------------------------------
    flow = get_required_approval_flow(template)

    if not flow:
        return JsonResponse(
            {
                "success": False,
                "message": "No approval flow configured for this template",
            },
            status=400,
        )

    approved = set(
        submission.approvals
        .filter(status="APPROVED")
        .values_list("category__code", flat=True)
    )

    current = next((c for c in flow if c not in approved), None)

    # --------------------------------------------------
    # 🔒 ORDER ENFORCEMENT
    # --------------------------------------------------
    if category.code != current:
        return JsonResponse(
            {
                "success": False,
                "error_type": "ORDER_BLOCKED",
                "message": f"{current} approval is required before {category.code}",
                "approval_flow": flow,
                "approved": sorted(approved),
                "pending": [c for c in flow if c not in approved],
            },
            status=400,
        )

    # --------------------------------------------------
    # PREVENT DUPLICATE APPROVAL
    # --------------------------------------------------
    if submission.approvals.filter(category=category).exists():
        return JsonResponse(
            {"success": False, "message": "Already approved"},
            status=400,
        )

    # --------------------------------------------------
    # CREATE APPROVAL RECORD
    # --------------------------------------------------
    # AUTO-FILL APPROVER NAME: user id + name
    full_name = request.user.get_full_name() or request.user.username
    default_approver_name = f"{request.user.username} {full_name}".strip()

    if engine == "CHECKLIST":
        approval = SubmissionApproval.objects.create(
            submission=submission,
            category=category,
            status="APPROVED",
            approver_name=default_approver_name,
        )
    else:
        approval = DynamicSubmissionApproval.objects.create(
            submission=submission,
            category=category,
            status="APPROVED",
            approver_name=default_approver_name,
        )

    approved.add(category.code)

    # --------------------------------------------------
    # WORKFLOW TRANSITION
    # --------------------------------------------------
    if set(flow).issubset(approved):
        submission.workflow_state = WorkflowState.CLOSED
        submission.save(update_fields=["workflow_state"])

    # --------------------------------------------------
    # 🔁 BITABLE UPDATE
    # --------------------------------------------------
    if engine == "CHECKLIST":
        update_approval_status_async(submission, approval)
    else:
        update_dynamic_approval_status_async(submission, approval)

    return JsonResponse(
        {
            "success": True,
            "engine": engine,
            "approved_category": category.code,
            "final_state": submission.workflow_state,
        }
    )

def public_submission_popup(request, token):

    submission = get_object_or_404(
        Submission.objects.select_related(
            "template_version",
            "work_context",
            "plant",
            "line",
            "product",
        ),
        public_approval_token=token,
    )

    sections = (
        submission.template_version.sections
        .prefetch_related("items")
        .order_by("order")
    )

    responses_qs = submission.responses.all()
    answers = {str(r.item_id): r.value for r in responses_qs}
    responses = {str(r.item_id): r for r in responses_qs}

    approval = getattr(submission, "approval", None)

    return render(
        request,
        "public/submission_popup.html",
        {
            "submission": submission,
            "sections": sections,
            "answers": answers,
            "responses": responses,
            "approval": approval,
        },
    )


@login_required
@transaction.atomic
def public_role_approval(request, token, category_code):
    """
    PUBLIC APPROVAL – CHECKLIST (CATEGORY-BASED)

    🔑 SECURITY FIX: Now requires login + role verification.
    Only users with the appropriate approval category role
    can submit approval (e.g., only PQE users can approve PQE step).
    """

    submission = get_object_or_404(
        Submission.objects.select_for_update(of=("self",)).select_related(
            "plant",
            "line",
            "product",
            "template_version__template",
        ),
        public_approval_token=token,
    )

    template = submission.template_version.template

    # --------------------------------------------------
    # 🔐 ROLE VERIFICATION (LOGIN REQUIRED)
    # --------------------------------------------------
    user = request.user
    full_name = user.get_full_name() or user.username
    default_approver_name = f"{user.username} {full_name}".strip()

    if not is_user_authorized_for_category(user, template, category_code):
        return render(request, "public/approval_page.html", {
            "error": f"You do not have permission to approve {category_code}. "
                     f"Please login with a {category_code} account.",
            "popup_url": reverse("ui:public_submission_popup", args=[submission.public_approval_token]),
            "default_approver_name": default_approver_name,
        })

    # --------------------------------------------------
    # VALIDATE APPROVAL CATEGORY
    # --------------------------------------------------
    try:
        category = ApprovalCategory.objects.get(
            code=category_code,
            is_active=True,
            is_approver=True,
        )
    except ApprovalCategory.DoesNotExist:
        return HttpResponseBadRequest("Invalid approval category")

    # --------------------------------------------------
    # REQUIRED APPROVAL STEPS (ORDERED)
    # --------------------------------------------------
    required_categories = get_required_approval_flow(template)

    if category.code not in required_categories:
        return HttpResponseForbidden("Approval not required for this category")

    # --------------------------------------------------
    # TERMINAL STATE GUARD
    # --------------------------------------------------
    if submission.workflow_state in WorkflowState.TERMINAL:
        return render(request, "public/approval_page.html", {
            "submission": submission,
            "role": category.code,
            "approval": None,
            "approvals": submission.approvals.all(),
            "error": "Submission already closed.",
            "popup_url": reverse(
                "ui:public_submission_popup",
                args=[submission.public_approval_token],
            ),
            "default_approver_name": default_approver_name,
        })

    # --------------------------------------------------
    # EXISTING APPROVAL
    # --------------------------------------------------
    existing = submission.approvals.filter(category=category).first()

    # --------------------------------------------------
    # APPROVAL ORDER ENFORCEMENT
    # --------------------------------------------------
    step_index = required_categories.index(category.code)

    for prior_code in required_categories[:step_index]:
        if not submission.approvals.filter(
            category__code=prior_code,
            status="APPROVED",
        ).exists():
            return render(request, "public/approval_page.html", {
                "submission": submission,
                "role": category.code,
                "approval": existing,
                "approvals": submission.approvals.all(),
                "error": f"{prior_code} approval required first.",
                "popup_url": reverse(
                    "ui:public_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

    # --------------------------------------------------
    # HANDLE POST
    # --------------------------------------------------
    if request.method == "POST" and not existing:

        status = request.POST.get("status")
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        approver_name = request.POST.get("approver_name", "").strip() or default_approver_name

        if status not in ["APPROVED", "REJECTED"]:
            return render(request, "public/approval_page.html", {
                "error": "Invalid status",
                "popup_url": reverse(
                    "ui:public_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

        if status == "REJECTED" and not rejection_reason:
            return render(request, "public/approval_page.html", {
                "error": "Rejection reason required",
                "popup_url": reverse(
                    "ui:public_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

        # --------------------------------------------------
        # CREATE APPROVAL
        # --------------------------------------------------
        approval = SubmissionApproval.objects.create(
            submission=submission,
            category=category,
            status=status,
            approver_name=approver_name,
            rejection_reason=rejection_reason,
        )

        # --------------------------------------------------
        # WORKFLOW TRANSITION
        # --------------------------------------------------
        if status == "REJECTED":
            submission.workflow_state = WorkflowState.FAILED
        else:
            approved_categories = set(
                submission.approvals.filter(
                    status="APPROVED",
                ).values_list("category__code", flat=True)
            )

            if set(required_categories).issubset(approved_categories):
                submission.workflow_state = WorkflowState.CLOSED

        submission.save(update_fields=["workflow_state"])

        # --------------------------------------------------
        # BITABLE STATUS UPDATE (ASYNC)
        # --------------------------------------------------
        update_approval_status_async(
            submission=submission,
            approval=approval,
        )

        existing = approval

    # --------------------------------------------------
    # FINAL RENDER
    # --------------------------------------------------
    return render(request, "public/approval_page.html", {
        "submission": submission,
        "role": category.code,
        "approval": existing,
        "approvals": submission.approvals.all(),
        "popup_url": reverse(
            "ui:public_submission_popup",
            args=[submission.public_approval_token],
        ),
        "default_approver_name": default_approver_name,
    })


@login_required
@transaction.atomic
def public_dynamic_role_approval(request, token, category_code):
    """
    PUBLIC APPROVAL – DYNAMIC FORMS (CATEGORY-BASED)

    🔑 SECURITY FIX: Now requires login + role verification.
    Only users with the appropriate approval category role
    can submit approval (e.g., only PQE users can approve PQE step).

    URL param:
    - category_code = ApprovalCategory.code (PD, PE, QA, SAFETY, etc.)
    """

    submission = get_object_or_404(
        DynamicFormSubmission.objects.select_for_update(),
        public_approval_token=token,
    )

    template = submission.template_version.template

    # --------------------------------------------------
    # 🔐 ROLE VERIFICATION (LOGIN REQUIRED)
    # --------------------------------------------------
    user = request.user
    full_name = user.get_full_name() or user.username
    default_approver_name = f"{user.username} {full_name}".strip()

    if not is_user_authorized_for_category(user, template, category_code):
        return render(request, "public/approval_page.html", {
            "error": f"You do not have permission to approve {category_code}. "
                     f"Please login with a {category_code} account.",
            "popup_url": reverse("ui:public_dynamic_submission_popup", args=[submission.public_approval_token]),
            "default_approver_name": default_approver_name,
        })

    # --------------------------------------------------
    # LOAD CATEGORY
    # --------------------------------------------------
    try:
        category = ApprovalCategory.objects.get(
            code=category_code,
            is_active=True,
            is_approver=True,
        )
    except ApprovalCategory.DoesNotExist:
        return HttpResponseBadRequest("Invalid approval category")

    # --------------------------------------------------
    # REQUIRED APPROVAL STEPS
    # --------------------------------------------------
    required_categories = get_required_approval_flow(template)

    if category.code not in required_categories:
        return HttpResponseForbidden("Approval not required for this category")

    # --------------------------------------------------
    # TERMINAL STATE GUARD
    # --------------------------------------------------
    if submission.workflow_state in WorkflowState.TERMINAL:
        return render(request, "public/approval_page.html", {
            "submission": submission,
            "role": category.code,
            "approval": None,
            "approvals": submission.approvals.select_related("category"),
            "error": "Submission already closed.",
            "popup_url": reverse(
                "ui:public_dynamic_submission_popup",
                args=[submission.public_approval_token],
            ),
            "default_approver_name": default_approver_name,
        })

    # --------------------------------------------------
    # EXISTING APPROVAL
    # --------------------------------------------------
    existing = submission.approvals.filter(category=category).first()

    # --------------------------------------------------
    # ORDER ENFORCEMENT
    # --------------------------------------------------
    step_index = required_categories.index(category.code)

    for prior_code in required_categories[:step_index]:
        if not submission.approvals.filter(
            category__code=prior_code,
            status="APPROVED",
        ).exists():
            return render(request, "public/approval_page.html", {
                "submission": submission,
                "role": category.code,
                "approval": existing,
                "approvals": submission.approvals.select_related("category"),
                "error": f"{prior_code} approval required first.",
                "popup_url": reverse(
                    "ui:public_dynamic_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

    # --------------------------------------------------
    # HANDLE POST
    # --------------------------------------------------
    if request.method == "POST" and not existing:

        status = request.POST.get("status")
        rejection_reason = request.POST.get("rejection_reason", "").strip()
        approver_name = request.POST.get("approver_name", "").strip() or default_approver_name

        if status not in ["APPROVED", "REJECTED"]:
            return render(request, "public/approval_page.html", {
                "error": "Invalid status",
                "popup_url": reverse(
                    "ui:public_dynamic_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

        if status == "REJECTED" and not rejection_reason:
            return render(request, "public/approval_page.html", {
                "error": "Rejection reason required",
                "popup_url": reverse(
                    "ui:public_dynamic_submission_popup",
                    args=[submission.public_approval_token],
                ),
                "default_approver_name": default_approver_name,
            })

        # --------------------------------------------------
        # CREATE APPROVAL (CATEGORY-BASED)
        # --------------------------------------------------
        approval = DynamicSubmissionApproval.objects.create(
            submission=submission,
            category=category,
            approver_role=None,  # optional (public approval)
            status=status,
            approver_name=approver_name,
            rejection_reason=rejection_reason,
        )

        # --------------------------------------------------
        # WORKFLOW TRANSITION
        # --------------------------------------------------
        if status == "REJECTED":
            submission.workflow_state = WorkflowState.FAILED
        else:
            approved_categories = set(
                submission.approvals.filter(
                    status="APPROVED"
                ).values_list("category__code", flat=True)
            )
            if set(required_categories).issubset(approved_categories):
                submission.workflow_state = WorkflowState.CLOSED

        submission.save(update_fields=["workflow_state"])

        # --------------------------------------------------
        # BITABLE STATUS UPDATE (ASYNC)
        # --------------------------------------------------
        update_dynamic_approval_status_async(
            submission=submission,
            approval=approval,
        )

        existing = approval

    # --------------------------------------------------
    # RENDER PAGE
    # --------------------------------------------------
    return render(request, "public/approval_page.html", {
        "submission": submission,
        "role": category.code,
        "approval": existing,
        "approvals": submission.approvals.select_related("category"),
        "popup_url": reverse(
            "ui:public_dynamic_submission_popup",
            args=[submission.public_approval_token],
        ),
        "default_approver_name": default_approver_name,
    })
    
def public_dynamic_submission_popup(request, token):
    """
    Public popup view for DYNAMIC FORM submissions
    (read-only, token based)
    """

    submission = get_object_or_404(
        DynamicFormSubmission.objects.select_related(
            "template_version",
            "work_context",
            "submitted_by",
        ).prefetch_related(
            "values__field",
        ),
        public_approval_token=token,
    )

    # --------------------------------------------------
    # Fields (ordered, from version)
    # --------------------------------------------------
    fields = (
        DynamicFormField.objects
        .filter(version=submission.template_version)
        .order_by("order")
    )

    # --------------------------------------------------
    # Values
    # --------------------------------------------------
    values_qs = submission.values.select_related("field")

    answers = {
        str(v.field_id): v.value
        for v in values_qs
    }

    responses = {
        str(v.field_id): v
        for v in values_qs
    }

    # --------------------------------------------------
    # Approvals (dynamic)
    # --------------------------------------------------
    approvals = submission.approvals.all()

    return render(
        request,
        "public/dynamic_submission_popup.html",
        {
            "submission": submission,
            "fields": fields,
            "answers": answers,
            "responses": responses,
            "approvals": approvals,
        },
    )