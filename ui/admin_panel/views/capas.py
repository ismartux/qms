from django.shortcuts import render, redirect, get_object_or_404
from django.forms import ModelForm
from django import forms
from django.core.exceptions import PermissionDenied

from ui.admin_panel.views.base import admin_required
from capa.models import CAPA


class CAPAForm(ModelForm):
    class Meta:
        model = CAPA
        fields = [
            "title", "description", "severity",
            "status", "due_date", "rca_summary"
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"})
        }


@admin_required
def capa_management(request):
    # ✅ Plant isolation handled automatically by PlantAwareManager
    capas = (
        CAPA.objects
        .all()
        .select_related("submission", "owner")
        .order_by("-created_at")
    )

    return render(request, "admin/capa_management.html", {"capas": capas})


@admin_required
def capa_create(request):
    form = CAPAForm(request.POST or None)

    if form.is_valid():
        capa = form.save(commit=False)

        # Optional safety: ensure plant consistency via submission
        if capa.submission:
            capa.plant = capa.submission.plant

        capa.save()
        return redirect("ui:admin_capas")

    return render(request, "admin/capa_form.html", {"form": form})


@admin_required
def capa_edit(request, capa_id):
    # ✅ This respects plant isolation automatically
    capa = get_object_or_404(CAPA.objects.all(), capa_id=capa_id)

    form = CAPAForm(request.POST or None, instance=capa)

    if form.is_valid():
        updated = form.save(commit=False)

        # Safety: prevent plant mismatch edits
        if updated.submission and updated.plant_id != updated.submission.plant_id:
            raise PermissionDenied("Plant mismatch detected.")

        updated.save()
        return redirect("ui:admin_capas")

    return render(request, "admin/capa_form.html", {
        "form": form,
        "capa": capa
    })