# ui/form_runtime/base.py

from abc import ABC, abstractmethod
from django.core.exceptions import ValidationError


class FormRuntimeAdapter(ABC):
    """
    🔑 Canonical runtime adapter contract.

    UI code MUST interact only with this interface.
    Engines (checklist / dynamic / future) MUST implement this fully.
    """

    engine_key: str  # e.g. "CHECKLIST", "DYNAMIC"

    # =====================================================
    # TEMPLATE / LISTING
    # =====================================================

    @abstractmethod
    def get_templates(self, *, work_context, user):
        """
        Returns a list of unified template dicts.

        REQUIRED SHAPE (minimum):
        {
            "id": str,
            "name": str,
            "engine": str,
            "description": str | None
        }
        """
        raise NotImplementedError

    @abstractmethod
    def get_template(self, *, template_id):
        """
        Fetch a single template instance (engine-specific model).
        """
        raise NotImplementedError

    # =====================================================
    # SUBMISSION LIFECYCLE
    # =====================================================

    @abstractmethod
    def get_or_create_draft(self, *, user, template, work_context):
        """
        Returns an editable draft submission.
        """
        raise NotImplementedError

    @abstractmethod
    def get_submission(self, *, submission_id, user):
        """
        Fetch a submission with access control.
        """
        raise NotImplementedError

    # =====================================================
    # RUNTIME SCHEMA
    # =====================================================

    @abstractmethod
    def build_runtime_schema(self, *, submission):
        """
        Must return UnifiedRuntimeSchema dict:

        {
            "template": {
                "code": str,
                "name": str,
                "version": str | int | None
            },
            "sections": [
                {
                    "key": str,
                    "label": str,
                    "order": int,
                    "fields": [...]
                }
            ]
        }

        🔹 Dynamic engines may return a single implicit section.
        """
        raise NotImplementedError

    # =====================================================
    # RUNTIME VALUES (🔥 REQUIRED)
    # =====================================================

    @abstractmethod
    def get_values(self, *, submission) -> dict:
        """
        Returns current values for runtime rendering.

        Checklist:
            { item_id (int): response_object }

        Dynamic:
            { field_key (str): value }

        UI must NOT care about engine differences.
        """
        raise NotImplementedError

    # =====================================================
    # MUTATION
    # =====================================================

    @abstractmethod
    def save_draft(self, *, submission, payload, files):
        """
        Persist draft data.

        Must NOT finalize submission.
        """
        raise NotImplementedError

    @abstractmethod
    def submit(self, *, submission, user):
        """
        Final submission.

        Must raise:
            ValidationError(list[str])
        on validation failure.
        """
        raise NotImplementedError

    # =====================================================
    # CAPABILITIES
    # =====================================================

    @abstractmethod
    def get_capabilities(self) -> dict:
        """
        Feature flags consumed by unified runtime UI.

        Expected keys:
        {
            "supports_sections": bool,
            "supports_partial_save": bool,
            "supports_attachments": bool,
            "supports_approvals": bool,
            "supports_scheduling": bool
        }
        """
        raise NotImplementedError