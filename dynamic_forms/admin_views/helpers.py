from django.shortcuts import get_object_or_404
from dynamic_forms.models import DynamicFormTemplate, DynamicFormVersion


def get_template_or_404(template_id):
    return get_object_or_404(
        DynamicFormTemplate,
        pk=template_id,
        is_archived=False,
    )


def get_version_or_404(version_id):
    return get_object_or_404(
        DynamicFormVersion,
        pk=version_id,
    )