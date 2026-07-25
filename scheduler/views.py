from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import (
    FormSchedule,
    ScheduledInstance,
    SchedulerControl,
)
from .forms import FormScheduleForm


# ======================================================
# ACCESS CONTROL
# ======================================================

def is_admin(user):
    return user.is_superuser or user.is_staff


# ======================================================
# SCHEDULE LIST
# ======================================================

@login_required
@user_passes_test(is_admin)
def schedule_list(request):

    schedules = FormSchedule.objects.select_related("template")

    return render(
        request,
        "scheduler_admin/schedule_list.html",
        {
            "schedules": schedules,
            "is_admin_panel": True,
        }
    )


# ======================================================
# CREATE
# ======================================================

@login_required
@user_passes_test(is_admin)
def schedule_create(request):

    if request.method == "POST":
        form = FormScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("scheduler_admin:schedule_list")
    else:
        form = FormScheduleForm()

    return render(
        request,
        "scheduler_admin/schedule_form.html",
        {
            "form": form,
            "is_admin_panel": True,
        }
    )


# ======================================================
# EDIT
# ======================================================

@login_required
@user_passes_test(is_admin)
def schedule_edit(request, pk):

    schedule = get_object_or_404(FormSchedule, pk=pk)

    if request.method == "POST":
        form = FormScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            form.save()
            return redirect("scheduler_admin:schedule_list")
    else:
        form = FormScheduleForm(instance=schedule)

    return render(
        request,
        "scheduler_admin/schedule_form.html",
        {
            "form": form,
            "schedule": schedule,
            "is_admin_panel": True,
        }
    )


# ======================================================
# INSTANCES
# ======================================================

@login_required
@user_passes_test(is_admin)
def instance_list(request):

    instances = (
        ScheduledInstance.objects
        .select_related("schedule", "schedule__template")
        .order_by("-expected_at")[:500]
    )

    return render(
        request,
        "scheduler_admin/instance_list.html",
        {
            "instances": instances,
            "is_admin_panel": True,
        }
    )


# ======================================================
# CONTROL
# ======================================================

@login_required
@user_passes_test(is_admin)
def scheduler_control(request):

    control, _ = SchedulerControl.objects.get_or_create(id=1)

    return render(
        request,
        "scheduler_admin/control.html",
        {
            "control": control,
            "is_admin_panel": True,
        }
    )
    
@login_required
@user_passes_test(is_admin)
def schedule_delete(request, pk):
    schedule = get_object_or_404(FormSchedule, pk=pk)

    if request.method == "POST":
        schedule.delete()
        return redirect("scheduler_admin:schedule_list")

    return render(
        request,
        "scheduler_admin/schedule_confirm_delete.html",
        {
            "schedule": schedule,
            "is_admin_panel": True,
        }
    )