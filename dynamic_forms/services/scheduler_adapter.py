from dynamic_forms.models import DynamicFormTemplate, DynamicFormVersion
from dynamic_forms.services.runtime_engine import DynamicFormRuntimeEngine


class DynamicFormSchedulerAdapter:
    """
    Adapter used by scheduler to create submissions
    from Dynamic Form Templates.

    Responsibility:
    - Resolve active published version
    - Build runtime schema snapshot
    - Return normalized payload for submission service
    """

    @staticmethod
    def get_active_version(
        template: DynamicFormTemplate,
    ) -> DynamicFormVersion:
        """
        Returns the single active + published version.
        Enforces strict safety: scheduler cannot run drafts.
        """
        try:
            return template.versions.get(
                is_active=True,
                is_published=True
            )
        except DynamicFormVersion.DoesNotExist:
            raise ValueError(
                f"No active published version for template {template.code}"
            )
        except DynamicFormVersion.MultipleObjectsReturned:
            raise ValueError(
                f"Multiple active published versions found for template {template.code}"
            )

    @staticmethod
    def build_submission_payload(
        template: DynamicFormTemplate,
        context: dict,
    ) -> dict:
        """
        Called by scheduler.

        Returns a normalized payload that the submissions
        application understands.

        This payload is a SNAPSHOT:
        - Runtime schema is frozen
        - Fields cannot change during submission lifecycle
        """

        version = DynamicFormSchedulerAdapter.get_active_version(template)

        # Build runtime schema (pure interpretation)
        engine = DynamicFormRuntimeEngine(version)
        runtime_schema = engine.build_runtime_schema()

        return {
            # -------------------------------------------------
            # TEMPLATE METADATA
            # -------------------------------------------------
            "template_type": "DYNAMIC_FORM",
            "template_code": template.code,
            "template_version": version.version_number,

            # -------------------------------------------------
            # ORGANIZATIONAL / SCHEDULER CONTEXT
            # -------------------------------------------------
            "plant_id": context.get("plant_id"),
            "shop_id": context.get("shop_id"),
            "department_id": template.department_id,
            "product_id": context.get("product_id"),
            "scheduled_at": context.get("scheduled_at"),

            # -------------------------------------------------
            # DYNAMIC FORM PAYLOAD
            # -------------------------------------------------
            "runtime_schema": runtime_schema,

            # Initial values are always empty at creation time.
            # User input / automation fills this later.
            "initial_values": {},
        }