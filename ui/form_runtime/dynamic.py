# ui/form_runtime/dynamic.py

from django.core.exceptions import ValidationError

from core.identity.context import get_user_role

from dynamic_forms.models import DynamicFormTemplate
from dynamic_forms.services.runtime_engine import DynamicFormRuntimeEngine
from dynamic_forms.services.submission_service import (
    get_or_create_dynamic_form_draft,
    save_dynamic_form_values,
    submit_dynamic_form_submission,
)

from ui.form_runtime.base import FormRuntimeAdapter


class DynamicFormsAdapter(FormRuntimeAdapter):
    engine_key = "DYNAMIC"

    # =====================================================
    # TEMPLATE LIST
    # =====================================================

    def get_templates(self, *, work_context, user):
        """
        Visibility-only filtering.
        Final permission enforcement happens in runtime views.
        """

        role = get_user_role(user, work_context=work_context)

        qs = (
            DynamicFormTemplate.objects
            .filter(
                is_active=True,
                is_archived=False,
                versions__is_active=True,
                versions__is_published=True,
            )
        )

        # -------------------------------------------------
        # CONTEXT MODE FILTER
        # -------------------------------------------------
        if work_context is None:
            # STANDALONE MODE
            qs = qs.filter(
                role_assignments__requires_work_context=False
            )
        else:
            # OPERATOR MODE
            qs = qs.filter(
                role_assignments__requires_work_context=True
            )

        # -------------------------------------------------
        # ROLE FILTER (VISIBILITY ONLY)
        # -------------------------------------------------
        if not user.is_superuser:
            if not role:
                return []

            qs = qs.filter(
                role_assignments__role=role
            )

        return [
            {
                "id": str(t.id),
                "code": t.code,
                "name": t.name,
                "description": t.description,
                "engine": self.engine_key,
            }
            for t in qs.distinct()
        ]

    # =====================================================
    # SINGLE TEMPLATE
    # =====================================================

    def get_template(self, *, template_id):
        """
        Fetch template safely.
        Publish + role enforcement happens elsewhere.
        """
        return DynamicFormTemplate.objects.get(
            id=template_id,
            is_active=True,
            is_archived=False,
        )

    # =====================================================
    # SUBMISSION
    # =====================================================

    def get_or_create_draft(self, *, user, template, work_context):
        """
        Draft creation respects role + context.
        """

        role = None
        if not user.is_superuser:
            role = get_user_role(user, work_context=work_context)

        return get_or_create_dynamic_form_draft(
            user=user,
            template=template,
            role=role,
            work_context=work_context,
        )

    def get_submission(self, *, submission_id, user):
        return user.dynamic_form_submissions.get(
            submission_id=submission_id
        )

    # =====================================================
    # RUNTIME SCHEMA
    # =====================================================

    def build_runtime_schema(self, *, submission):
        """
        Dynamic runtime schema normalized for unified runtime UI.
        """

        engine = DynamicFormRuntimeEngine(
            version=submission.template_version,
            preview=False,
        )

        raw = engine.build_runtime_schema()

        normalized_fields = [
            {
                **f,
                "key": f"field_{f['id']}",
            }
            for f in raw["fields"]
        ]

        return {
            "template": {
                "code": raw["template_code"],
                "name": raw["template_name"],
                "version": raw["version"],
            },
            "fields": normalized_fields,
            "sections": [
                {
                    "key": "main",
                    "label": "Main",
                    "order": 1,
                    "fields": normalized_fields,
                }
            ],
        }

    # =====================================================
    # VALUES
    # =====================================================

    def get_values(self, *, submission) -> dict:
        return {
            str(v.field_id): v.value
            for v in submission.values.all()
        }

    # =====================================================
    # MUTATION
    # =====================================================

    def save_draft(self, *, submission, payload, files):
        save_dynamic_form_values(
            submission=submission,
            payload=payload,
            files=files,
        )

    def submit(self, *, submission, user):
        try:
            return submit_dynamic_form_submission(
                submission=submission,
                user=user,
            )
        except ValidationError as e:
            raise ValidationError(e.messages)

    # =====================================================
    # CAPABILITIES
    # =====================================================

    def get_capabilities(self):
        return {
            "supports_sections": False,
            "supports_partial_save": True,
            "supports_attachments": True,
            "supports_approvals": True,
            "supports_scheduling": True,
        }