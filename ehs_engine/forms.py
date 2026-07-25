from django import forms
from .models import EHSSubmission


class RiskForm(forms.Form):
    likelihood = forms.IntegerField(min_value=1, max_value=5)
    severity = forms.IntegerField(min_value=1, max_value=5)