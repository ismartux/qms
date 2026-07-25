from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from forms_engine.decorators import admin_required
from forms_engine.models import ChecklistTemplate


@login_required
@admin_required
def dashboard(request):

    user = request.user
    work_context = getattr(user, "active_work_context", None)

    # ---------------------------------------------
    # SUPERUSER → See all templates
    # ---------------------------------------------
    if user.is_superuser:
        templates = (
            ChecklistTemplate.objects
            .prefetch_related(
                "versions",
                "plants",
                "shops",
                "role_assignments__role",
            )
            .select_related("department")
            .order_by("-created_at")
        )

    # ---------------------------------------------
    # PLANT-SCOPED ADMIN
    # ---------------------------------------------
    else:
        if not work_context:
            templates = ChecklistTemplate.objects.none()
        else:
            templates = (
                ChecklistTemplate.objects
                .filter(plants=work_context.plant)
                .prefetch_related(
                    "versions",
                    "plants",
                    "shops",
                    "role_assignments__role",
                )
                .select_related("department")
                .distinct()
                .order_by("-created_at")
            )

    return render(
        request,
        "forms_builder/dashboard.html",
        {
            "templates": templates,
            "mode": "admin",
        },
    )