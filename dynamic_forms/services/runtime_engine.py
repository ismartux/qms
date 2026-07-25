from typing import Dict, List, Any
from django.core.cache import cache
import time

from dynamic_forms.models import (
    DynamicFormVersion,
    DynamicFormField,
    DynamicFormStandardRule,
)
from integrations.bitable.read_service import fetch_bitable_rows
import requests
from django.conf import settings

# =========================================================
# RUNTIME FIELD (IN-MEMORY ONLY)
# =========================================================
class RuntimeField:
    def __init__(
        self,
        *,
        field_id: int,
        label: str,
        field_kind: str,
        data_type: str,
        required: bool,
        options: List[Any] = None,
        min_value=None,
        max_value=None,
        dependency: Dict[str, Any] = None,
        reference: Dict[str, Any] = None,
        read_only: bool = False,
        help_text: str = "",
    ):
        self.field_id = field_id
        self.label = label
        self.field_kind = field_kind
        self.data_type = data_type
        self.required = required
        self.options = options or []
        self.min_value = min_value
        self.max_value = max_value
        self.dependency = dependency
        self.reference = reference
        self.read_only = read_only
        self.help_text = help_text

    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.field_id,
            "label": self.label,
            "field_kind": self.field_kind,
            "type": self.data_type,
            "required": self.required,
            "help_text": self.help_text,
            "options": self.options,
            "min": self.min_value,
            "max": self.max_value,
            "dependency": self.dependency,
            "reference": self.reference,
            "read_only": self.read_only,
        }


# =========================================================
# DYNAMIC FORM RUNTIME ENGINE
# =========================================================
class DynamicFormRuntimeEngine:
    """
    Stateless runtime interpreter.

    - Reads DynamicFormField
    - Reads DynamicFormStandardRule
    - Reads Bitable rows (cached)
    - Handles dropdown dependency + standard values
    """

    def __init__(self, version: DynamicFormVersion, preview: bool = False):
        self.version = version
        self.template = version.template
        self.preview = preview

        self.fields: List[DynamicFormField] = list(
            version.fields.all().order_by("order")
        )

        self.standard_rules: List[DynamicFormStandardRule] = list(
            version.standard_rules.select_related("target_field")
        )

        if self.preview:
            self.source_rows: List[Dict[str, Any]] = []
        else:
            self.source_rows = self._fetch_source_rows()

        # injected dynamically during runtime
        self._submission_context: Dict[str, Any] = {}

    # -----------------------------------------------------
    # ENTRY POINT
    # -----------------------------------------------------
    def build_runtime_schema(self) -> Dict[str, Any]:
        runtime_fields = [
            self._build_runtime_field(field)
            for field in self.fields
        ]

        return {
            "template_code": self.template.code,
            "template_name": self.template.name,
            "version": self.version.version_number,
            "fields": [f.serialize() for f in runtime_fields],
        }

    # -----------------------------------------------------
    # SOURCE DATA (CACHED)
    # -----------------------------------------------------
    def _fetch_source_rows(self):
        cache_key = f"dynamic_forms:bitable_rows:{self.template.id}"


        rows = cache.get(cache_key)
        if rows is not None:
            return rows


        try:
            requests.post(
                settings.CLOUDFLARE_READ_WORKER_URL,
                json={
                    # 🔑 UUID → STRING
                    "template_id": str(self.template.id),
                    "app_token": self.template.source_bitable_app_token,
                    "table_id": self.template.source_bitable_table_id,
                },
                timeout=5,
            )
        except Exception as e:
            print("❌ Failed to trigger Cloudflare:", e)
            return []

        # ⏳ wait for snapshot (max 5 sec)
        for i in range(10):
            time.sleep(0.5)
            rows = cache.get(cache_key)
            if rows is not None:
                return rows

        return []

    # -----------------------------------------------------
    # FIELD BUILDER
    # -----------------------------------------------------
    def _build_runtime_field(self, field: DynamicFormField) -> RuntimeField:
        options = []
        min_value = None
        max_value = None
        dependency = None
        reference = None

        if field.data_type == "DROPDOWN":
            options = self._resolve_dropdown_options(field)

        if field.data_type == "NUMBER":
            min_value, max_value = self._resolve_number_constraints(field)

        if field.depends_on_field_id:
            dependency = {
                "depends_on": field.depends_on_field_id,
                **(field.dependency_config or {}),
            }

        if field.reference_config.get("enabled"):
            reference = field.reference_config

        return RuntimeField(
            field_id=field.id,
            label=field.label,
            field_kind=field.field_kind,
            data_type=field.data_type,
            required=field.required,
            options=options,
            min_value=min_value,
            max_value=max_value,
            dependency=dependency,
            reference=reference,
            read_only=field.field_kind == "SUPPORT",
            help_text=field.help_text,
        )

    # -----------------------------------------------------
    # DROPDOWN HELPERS
    # -----------------------------------------------------
    def _resolve_dropdown_options(self, field: DynamicFormField) -> List[Any]:
        config = field.dropdown_config or {}
        source_type = config.get("source")

        if source_type == "manual":
            return config.get("options", [])

        if source_type == "auto" and field.bitable_column_id:
            filters = self._resolve_dependency_chain(field)

            values = set()
            for row in self.source_rows:
                if not self._row_matches_filters(row, filters):
                    continue

                val = row.get(field.bitable_column_id)
                if val not in (None, ""):
                    values.add(val)

            return sorted(values)

        return []

    def _resolve_dependency_chain(self, field: DynamicFormField) -> List[Dict[str, Any]]:
        filters = []
        current = field

        while current.depends_on_field:
            parent = current.depends_on_field

            parent_column = (
                current.dependency_config or {}
            ).get("parent_column")

            if parent_column:
                filters.append({
                    "column": parent_column,
                    "field_id": parent.id,
                })

            current = parent

        return filters

    def _row_matches_filters(
        self,
        row: Dict[str, Any],
        filters: List[Dict[str, Any]],
    ) -> bool:
        for f in filters:
            submitted_value = self._submission_context.get(
                str(f["field_id"])
            )
            if submitted_value in (None, ""):
                return False
            if str(row.get(f["column"], "")).strip() != str(submitted_value).strip():
                return False
        return True

    # -----------------------------------------------------
    # NUMBER HELPERS
    # -----------------------------------------------------
    def _resolve_number_constraints(self, field: DynamicFormField):
        config = field.number_config or {}
        return (
            self._resolve_number_value(config.get("min")),
            self._resolve_number_value(config.get("max")),
        )

    def _resolve_number_value(self, config):
        if not config:
            return None

        if config.get("type") == "static":
            return config.get("value")

        if config.get("type") == "column":
            for row in self.source_rows:
                if config.get("value") in row:
                    return row.get(config.get("value"))

        return None

    # =====================================================
    # STANDARD RULE EVALUATION (UI + VALIDATION)
    # =====================================================
    def evaluate_standard_rules(
        self,
        submission_values: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        self._submission_context = {
            str(k): v for k, v in submission_values.items()
        }

        results = []

        for rule in self.standard_rules:
            field_id = str(rule.target_field.id)

            actual = submission_values.get(field_id)
            standard = self._resolve_standard_value(rule)

            # 🔑 STANDARD MUST BE SHOWN EVEN IF ACTUAL IS EMPTY
            if standard is None:
                continue

            passed = True
            if actual not in (None, ""):
                passed = self._compare(actual, standard, rule.operator)

            results.append({
                "field_id": rule.target_field.id,
                "field_label": rule.target_field.label,
                "actual": actual,
                "standard": standard,
                "operator": rule.operator,
                "passed": passed,
                "source": rule.value_source,
            })

        return results

    # =====================================================
    # STANDARD VALUE RESOLUTION
    # =====================================================
    def _resolve_standard_value(self, rule: DynamicFormStandardRule):
        """
        Resolve standard value so it can be SHOWN to the user.
        Supports MANUAL and BITABLE (with dependency filters)
        """

        if rule.value_source == "MANUAL":
            return rule.manual_value

        for row in self.source_rows:
            matched = True

            for dep in rule.dependency_filters:
                field_id = str(dep.get("field_id"))
                column = dep.get("bitable_column")

                if not field_id or not column:
                    matched = False
                    break

                submitted_value = self._submission_context.get(field_id)

                # 🔑 Allow dependency-based standard resolution
                if submitted_value is None:
                    matched = False
                    break

                row_value = row.get(column)
                if row_value in (None, ""):
                    matched = False
                    break

                if str(row_value).strip() != str(submitted_value).strip():
                    matched = False
                    break

            if not matched:
                continue

            standard = row.get(rule.bitable_column_id)
            if standard in (None, ""):
                return None

            return standard

        return None

    # -----------------------------------------------------
    # NUMERIC NORMALIZATION (NEW – SAFE)
    # -----------------------------------------------------
    def _normalize_numeric(self, value):
        """
        Converts '90%', ' 93 % ', '90.0' → float
        Returns None if conversion fails
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        try:
            return float(str(value).replace("%", "").strip())
        except Exception:
            return None

    # -----------------------------------------------------
    # COMPARISON (FIXED FOR % VALUES)
    # -----------------------------------------------------
    def _compare(self, actual, standard, operator: str) -> bool:
        actual_val = self._normalize_numeric(actual)
        standard_val = self._normalize_numeric(standard)

        if actual_val is None or standard_val is None:
            return False

        if operator == "EQ":
            return actual_val == standard_val
        if operator == "LTE":
            return actual_val <= standard_val
        if operator == "GTE":
            return actual_val >= standard_val

        return False