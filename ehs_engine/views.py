from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from core.identity.permissions import has_permission
from ehs_engine.models import (
    EHSFormTemplate,
    RiskAssessment,
    EHSSubmission,
    EHSResponse,
    EHSNotification,
)
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from config import settings
from django.utils import timezone
from django.utils.dateparse import parse_date


def create_notification(user, title, message, submission=None):
    EHSNotification.objects.create(
        recipient=user,
        title=title,
        message=message,
        submission=submission
    )

# =========================================================
# TEMPLATE LIST (AUDITOR VIEW)
# =========================================================

def ehs_daily_template_list(request):

    if not has_permission(request.user, "can_fill_ehs_forms"):
        raise PermissionDenied("You do not have permission to access EHS forms.")

    templates = (
        EHSFormTemplate.objects
        .filter(
            is_active=True,
            is_archived=False,
            template_type=EHSFormTemplate.DAILY,
            versions__is_active=True,
            versions__is_published=True
        )
        .distinct()
        .prefetch_related("versions")
    )

    return render(
        request,
        "ehs_engine/auditor/template_list.html",
        {
            "templates": templates,
            "page_type": "DAILY"
        }
    )

def ehs_special_template_list(request):

    if not has_permission(request.user, "can_fill_ehs_forms"):
        raise PermissionDenied("You do not have permission to access EHS forms.")

    templates = (
        EHSFormTemplate.objects
        .filter(
            is_active=True,
            is_archived=False,
            template_type=EHSFormTemplate.SPECIAL,
            versions__is_active=True,
            versions__is_published=True
        )
        .distinct()
        .prefetch_related("versions")
    )

    return render(
        request,
        "ehs_engine/auditor/template_list.html",
        {
            "templates": templates,
            "page_type": "SPECIAL"
        }
    )

# =========================================================
# START SUBMISSION
# =========================================================

def ehs_start_submission(request, template_id):

    if not has_permission(request.user, "can_fill_ehs_forms"):
        raise PermissionDenied("You do not have permission to start EHS submissions.")

    template = get_object_or_404(EHSFormTemplate, pk=template_id)

    version = template.versions.filter(
        is_active=True,
        is_published=True
    ).first()

    # ----------------------------
    # HANDLE NO VERSION
    # ----------------------------
    if not version:
        messages.error(request, "No active version available.")

        if template.template_type == EHSFormTemplate.SPECIAL:
            return redirect("ehs:ehs_special_template_list")
        else:
            return redirect("ehs:ehs_daily_template_list")

    # ----------------------------
    # SAFE PLANT RESOLUTION
    # ----------------------------

    plant = None

    scope = request.user.scopes.select_related("plant").first()
    if scope:
        plant = scope.plant
    elif request.user.is_superuser:
        plant = template.plants.first()

    if not plant:
        messages.error(request, "No plant assigned to this user or template.")

        if template.template_type == EHSFormTemplate.SPECIAL:
            return redirect("ehs:ehs_special_template_list")
        else:
            return redirect("ehs:ehs_daily_template_list")

    # ----------------------------
    # CREATE SUBMISSION
    # ----------------------------

    submission = EHSSubmission.objects.create(
        version=version,
        plant=plant,
        reported_by=request.user,
        status="DRAFT"
    )

    return redirect("ehs:fill_submission", pk=submission.pk)


# =========================================================
# FILL SUBMISSION
# =========================================================

def ehs_fill_submission(request, pk):

    if not has_permission(request.user, "can_fill_ehs_forms"):
        raise PermissionDenied("You do not have permission to fill EHS forms.")

    submission = get_object_or_404(EHSSubmission, pk=pk)

    # ---------------------------------------------------------
    # LOCKED SUBMISSION
    # ---------------------------------------------------------
    from django.urls import reverse
    if submission.status != "DRAFT":

        if submission.version.template.template_type == EHSFormTemplate.SPECIAL:
            dashboard_url = reverse("ehs:ehs_special_template_list")
        else:
            dashboard_url = reverse("ehs:ehs_daily_template_list")

        return render(
            request,
            "ehs_engine/auditor/submitted.html",
            {
                "submission": submission,
                "dashboard_url": dashboard_url,
            },
        )

    version = submission.version

    # ---------------------------------------------------------
    # SECTIONS
    # ---------------------------------------------------------
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
    except ValueError:
        step = 1

    if step < 1 or step > total_steps:
        raise Http404("Invalid step")

    current_section = sections[step - 1]

    # ---------------------------------------------------------
    # POST
    # ---------------------------------------------------------
    if request.method == "POST":

        missing_items = []

        with transaction.atomic():

            for item in current_section.items.all():

                value = request.POST.get(f"item_{item.id}")
                remark = request.POST.get(f"item_remark_{item.id}")
                file_base = request.FILES.get(f"item_file_{item.id}")

                # ===============================
                # RISK MATRIX
                # ===============================
                if item.item_type == "RISK_MATRIX":

                    likelihood = request.POST.get("risk_likelihood")
                    severity = request.POST.get("risk_severity")

                    if item.required and (not likelihood or not severity):
                        missing_items.append(item)
                        continue

                    if likelihood and severity:
                        RiskAssessment.objects.update_or_create(
                            submission=submission,
                            defaults={
                                "likelihood": likelihood,
                                "severity": severity,
                            }
                        )
                    continue

                # ===============================
                # REQUIRED FIELD CHECK
                # ===============================
                if item.required and not value and not file_base:
                    missing_items.append(item)
                    continue

                # ===============================
                # RULE CONDITION CHECK
                # ===============================
                rules = item.rules.all()

                photo_required = False
                remark_required = False
                escalate_required = False

                for rule in rules:
                    if rule.condition_value == value:

                        if rule.rule_type == "PHOTO_REQUIRED":
                            photo_required = True

                        if rule.rule_type == "REMARK_REQUIRED":
                            remark_required = True

                        if rule.rule_type == "ESCALATE":
                            escalate_required = True

                # If rule triggered but missing required fields
                if photo_required and not file_base:
                    missing_items.append(item)
                    continue

                if remark_required and not remark:
                    missing_items.append(item)
                    continue

                # ===============================
                # Skip if empty draft
                # ===============================
                if not value and not remark and not file_base:
                    continue

                # ===============================
                # SAVE RESPONSE
                # ===============================
                response, _ = EHSResponse.objects.get_or_create(
                    submission=submission,
                    item=item,
                )

                response.value = value
                response.remark = remark or ""

                if file_base:
                    response.photo = file_base

                response.save()

                # ===============================
                # ESCALATION LOGIC
                # ===============================
                if escalate_required:
                    # You can customize this behavior
                    submission.status = "UNDER_REVIEW"

            # ===============================
            # STOP IF VALIDATION FAILED
            # ===============================
            if missing_items:
                messages.error(
                    request,
                    "Please complete required fields triggered by rules before continuing."
                )
                request.session["missing_item_ids"] = [
                    item.id for item in missing_items
                ]
                return redirect(f"{request.path}?step={step}")

            # ===============================
            # NEXT STEP
            # ===============================
            if step < total_steps:
                return redirect(f"{request.path}?step={step + 1}")

            # ===============================
            # FINAL SUBMIT
            # ===============================
            submission.status = (
                "UNDER_REVIEW"
                if submission.version.template.require_approval
                else "SUBMITTED"
            )
            submission.save()

            create_notification(
                submission.reported_by,
                title="Submission Submitted",
                message=f"Your submission for {submission.version.template.name} has been submitted.",
                submission=submission
            )

            if submission.version.template.template_type == EHSFormTemplate.SPECIAL:
                return redirect("ehs:ehs_special_template_list")
            else:
                return redirect("ehs:ehs_daily_template_list")

    # ---------------------------------------------------------
    # GET STATE
    # ---------------------------------------------------------
    missing_item_ids = request.session.pop("missing_item_ids", [])

    responses_by_item = {
        r.item_id: r
        for r in submission.responses.all()
    }

    risk_assessment = getattr(submission, "risk_assessment", None)

    return render(
        request,
        "ehs_engine/auditor/runtime.html",
        {
            "template": version.template,
            "version": version,
            "section": current_section,
            "step": step,
            "total_steps": total_steps,
            "submission": submission,
            "missing_item_ids": missing_item_ids,
            "responses_by_item": responses_by_item,
            "risk_assessment": risk_assessment,
        },
    )

# =========================================================
# SUBMIT SUBMISSION
# =========================================================

def ehs_submit_submission(request, pk):

    if not has_permission(request.user, "can_submit_ehs"):
        raise PermissionDenied("You do not have permission to submit EHS forms.")

    submission = get_object_or_404(EHSSubmission, pk=pk)

    if submission.status != "DRAFT":
        messages.error(request, "Submission already processed.")
        if submission.version.template.template_type == EHSFormTemplate.SPECIAL:
            return redirect("ehs:ehs_special_template_list")
        else:
            return redirect("ehs:ehs_daily_template_list")

    try:
        with transaction.atomic():

            # Ensure all required items answered
            required_items = submission.version.sections \
                .prefetch_related("items") \
                .values_list("items__id", flat=True)

            answered_items = submission.responses.values_list("item_id", flat=True)

            missing = set(required_items) - set(answered_items)

            if missing:
                raise ValidationError("All items must be answered before submitting.")

            submission.status = (
                "UNDER_REVIEW"
                if submission.version.template.require_approval
                else "SUBMITTED"
            )

            submission.save()

            create_notification(
                submission.reported_by,
                title="Submission Submitted",
                message=f"Your submission for {submission.version.template.name} has been submitted.",
                submission=submission
            )

        messages.success(request, "Submission submitted successfully.")

    except ValidationError as e:
        messages.error(request, e)

    except Exception as e:
        messages.error(request, f"Error submitting: {str(e)}")

    if submission.version.template.template_type == EHSFormTemplate.SPECIAL:
        return redirect("ehs:ehs_special_template_list")
    else:
        return redirect("ehs:ehs_daily_template_list")


@login_required
def ehs_qr_scanner(request):
    return render(request, "ehs_engine/qr_scanner.html")



@login_required
def ehs_submission_list(request):

    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied

    submission_type = request.GET.get("type", "DAILY")  # default Daily

    submissions = (
        EHSSubmission.objects
        .select_related("version__template", "plant", "reported_by")
        .filter(
            version__template__template_type=submission_type
        )
        .order_by("-created_at")
    )

    # ================= SIMPLE PERMISSION FILTER =================
    if not request.user.is_superuser:
        submissions = submissions.filter(reported_by=request.user)

    # ================= KPI =================
    total_count = submissions.count()
    avg_risk = submissions.aggregate(avg=Avg("risk_score"))["avg"] or 0
    high_risk_count = submissions.filter(risk_score__gte=8).count()

    # ================= PAGINATION =================
    per_page = int(request.GET.get("per_page", 12))
    paginator = Paginator(submissions, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "ehs_engine/submissions/list.html",
        {
            "page_obj": page_obj,
            "submission_type": submission_type,
            "total_count": total_count,
            "avg_risk": avg_risk,
            "high_risk_count": high_risk_count,
        },
    )

@login_required
def ehs_submission_popup(request, pk):

    submission = get_object_or_404(
        EHSSubmission.objects.select_related(
            "version__template",
            "plant",
            "reported_by",
        ).prefetch_related("responses__item"),
        pk=pk,
    )

    EHSNotification.objects.filter(
        recipient=request.user,
        submission=submission,
        is_read=False
    ).update(is_read=True)

    sections = (
        submission.version.sections
        .prefetch_related("items")
        .order_by("order")
    )

    responses_qs = submission.responses.all()

    answers = {str(r.item_id): r.value for r in responses_qs}
    responses = {str(r.item_id): r for r in responses_qs}

    return render(
        request,
        "ehs_engine/submissions/popup.html",
        {
            "submission": submission,
            "sections": sections,
            "answers": answers,
            "responses": responses,
        },
    )

@login_required
def ehs_mark_notification_read(request, pk):

    notification = get_object_or_404(
        EHSNotification,
        pk=pk,
        recipient=request.user
    )

    notification.is_read = True
    notification.save(update_fields=["is_read"])

    return redirect(request.META.get("HTTP_REFERER", "/"))


@login_required
def ehs_notification_list(request):

    notifications = EHSNotification.objects.filter(
        recipient=request.user
    ).order_by("-created_at")

    return render(
        request,
        "ehs_engine/notifications/list.html",
        {
            "notifications": notifications
        }
    )


@login_required
def ehs_home(request):

    if not has_permission(request.user, "can_fill_ehs_forms"):
        raise PermissionDenied

    today = timezone.now().date()

    # =========================
    # ACTIVE DRAFT (Current Session Equivalent)
    # =========================
    active_submission = (
        EHSSubmission.objects
        .select_related("version__template", "plant")
        .filter(
            reported_by=request.user,
            status="DRAFT"
        )
        .order_by("-created_at")
        .first()
    )

    # =========================
    # RECENT SUBMISSIONS
    # =========================
    recent_submissions = (
        EHSSubmission.objects
        .select_related("version__template", "plant")
        .filter(reported_by=request.user)
        .exclude(status="DRAFT")
        .order_by("-created_at")[:10]
    )

    # =========================
    # KPI
    # =========================
    submissions = EHSSubmission.objects.filter(
        reported_by=request.user
    )

    total_count = submissions.count()
    avg_risk = submissions.aggregate(avg=Avg("risk_score"))["avg"] or 0
    high_risk_count = submissions.filter(risk_score__gte=8).count()

    # =========================
    # TEMPLATE COUNTS
    # =========================
    daily_templates = EHSFormTemplate.objects.filter(
        template_type=EHSFormTemplate.DAILY,
        is_active=True,
        is_archived=False
    ).count()

    special_templates = EHSFormTemplate.objects.filter(
        template_type=EHSFormTemplate.SPECIAL,
        is_active=True,
        is_archived=False
    ).count()

    return render(
        request,
        "ehs_engine/home.html",
        {
            "active_submission": active_submission,
            "recent_submissions": recent_submissions,
            "total_count": total_count,
            "avg_risk": round(avg_risk, 2),
            "high_risk_count": high_risk_count,
            "daily_templates": daily_templates,
            "special_templates": special_templates,
        }
    )


@login_required
def ehs_admin_submission_list(request):

    if not has_permission(request.user, "can_manage_ehs_templates"):
        raise PermissionDenied("You do not have admin permission.")

    submissions = (
        EHSSubmission.objects
        .select_related(
            "version__template",
            "plant",
            "reported_by"
        )
        .order_by("-created_at")
    )

    # ===============================
    # FILTERS
    # ===============================

    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    template_type = request.GET.get("template_type")
    status = request.GET.get("status")
    plant_id = request.GET.get("plant")

    if start_date:
        submissions = submissions.filter(created_at__date__gte=parse_date(start_date))

    if end_date:
        submissions = submissions.filter(created_at__date__lte=parse_date(end_date))

    if template_type:
        submissions = submissions.filter(
            version__template__template_type=template_type
        )

    if status:
        submissions = submissions.filter(status=status)

    if plant_id:
        submissions = submissions.filter(plant_id=plant_id)

    # ===============================
    # KPI
    # ===============================

    total_count = submissions.count()
    avg_risk = submissions.aggregate(avg=Avg("risk_score"))["avg"] or 0
    high_risk = submissions.filter(risk_score__gte=8).count()

    # ===============================
    # PAGINATION
    # ===============================

    per_page = int(request.GET.get("per_page", 20))
    paginator = Paginator(submissions, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "ehs_engine/admin/submission_list.html",
        {
            "page_obj": page_obj,
            "total_count": total_count,
            "avg_risk": round(avg_risk, 2),
            "high_risk": high_risk,
            "filters": request.GET,
        }
    )