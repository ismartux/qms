# ui/form_runtime/checklist.py

from django.core.exceptions import ValidationError
from django.db.models import Q
from core.identity.context import get_user_scope
from forms_engine.models import ChecklistTemplate

from submissions.services import (
    get_or_create_draft_submission,
    save_submission_responses,
    submit_submission,
)

from ui.form_runtime.base import FormRuntimeAdapter


class ChecklistAdapter(FormRuntimeAdapter):
    engine_key = "CHECKLIST"

    # =====================================================
    # TEMPLATE LIST
    # =====================================================

    def get_templates(self, *, work_context, user):

        scope = get_user_scope(user, work_context=work_context)
        role = scope.role if scope else None

        if not role and not user.is_superuser:
            return []

        qs = (
            ChecklistTemplate.objects
            .filter(
                is_active=True,
                is_archived=False,
                versions__is_active=True,
                versions__is_published=True,
            )
            .filter(
                Q(plants__isnull=True) | Q(plants=work_context.plant),
                Q(shops__isnull=True) | Q(shops=work_context.shop),
                Q(products__isnull=True) | Q(products=work_context.product),
            )
        )

        # 🔐 ROLE FILTER
        if not user.is_superuser:
            qs = qs.filter(role_assignments__role=role)

        qs = qs.distinct()

        return [
            {
                "id": str(t.id),
                "code": t.code,
                "name": t.name,
                "description": t.description,
                "engine": self.engine_key,
            }
            for t in qs
        ]

    def get_template(self, *, template_id):
        return ChecklistTemplate.objects.get(
            id=template_id,
            is_active=True,
            is_archived=False,
        )

    # =====================================================
    # SUBMISSION
    # =====================================================

    def get_or_create_draft(self, *, user, template, work_context):
        return get_or_create_draft_submission(
            user,
            template,
            work_context,
        )

    def get_submission(self, *, submission_id, user):
        return user.submissions.get(
            submission_id=submission_id
        )

    # =====================================================
    # RUNTIME SCHEMA
    # =====================================================

    def build_runtime_schema(self, *, submission):

        version = submission.template_version

        sections = []

        for section in (
            version.sections
            .prefetch_related("items__options")
            .order_by("order")
        ):
            sections.append({
                "key": str(section.id),
                "label": section.title,   # ✅ matches template usage
                "order": section.order,
                "fields": [
                    {
                        "id": item.id,
                        "label": item.label,
                        "type": item.item_type,
                        "required": item.required,
                        "help_text": "",
                        "options": [
                            opt.value for opt in item.options.all()
                        ],
                        "dependency": None,
                        "reference": None,
                        "read_only": False,
                    }
                    for item in section.items.all()
                ],
            })

        return {
            "template": {
                "code": version.template.code,
                "name": version.template.name,
                "version": version.version_number,
            },
            "sections": sections,
        }

    # =====================================================
    # VALUES (🔥 THIS WAS MISSING)
    # =====================================================

    def get_values(self, *, submission) -> dict:
        """
        Returns current checklist values in unified format:
        { item_id (str): value }
        """

        values = {}

        for r in submission.responses.all():
            try:
                values[str(r.item_id)] = r.value
            except Exception:
                continue

        return values

    # =====================================================
    # MUTATION
    # =====================================================

    def save_draft(self, *, submission, payload, files):
        save_submission_responses(
            submission,
            payload,
            files,
        )

    def submit(self, *, submission, user):
        try:
            return submit_submission(submission, user)
        except ValidationError as e:
            raise ValidationError(e.messages)

    # =====================================================
    # CAPABILITIES
    # =====================================================

    def get_capabilities(self):
        return {
            "supports_sections": True,
            "supports_partial_save": True,
            "supports_attachments": True,
            "supports_approvals": True,
            "supports_scheduling": True,
        }