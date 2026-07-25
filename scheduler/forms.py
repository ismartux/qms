# scheduler/forms.py
from django import forms
from .models import FormSchedule


class FormScheduleForm(forms.ModelForm):

    class Meta:
        model = FormSchedule
        fields = [
            "template",
            "schedule_type",
            "interval_minutes",
            "times_per_shift",
            "daily_time",
            "is_active",
        ]

        widgets = {
            "template": forms.Select(attrs={
                "class": "form-field"
            }),
            "schedule_type": forms.Select(attrs={
                "class": "form-field"
            }),
            "interval_minutes": forms.NumberInput(attrs={
                "class": "form-field",
                "placeholder": "e.g. 30"
            }),
            "times_per_shift": forms.NumberInput(attrs={
                "class": "form-field",
                "placeholder": "e.g. 2"
            }),
            "daily_time": forms.TimeInput(attrs={
                "type": "time",
                "class": "form-field"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-checkbox"
            }),
        }