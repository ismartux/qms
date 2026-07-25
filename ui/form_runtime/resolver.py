# ui/form_runtime/resolver.py

from ui.form_runtime.checklist import ChecklistAdapter
from ui.form_runtime.dynamic import DynamicFormsAdapter


# -----------------------------------------------------
# Adapter registry (CLASS REFERENCES, NOT INSTANCES)
# -----------------------------------------------------

_ADAPTER_CLASSES = {
    "CHECKLIST": ChecklistAdapter,
    "DYNAMIC": DynamicFormsAdapter,
}


def resolve_adapter(engine_key: str):
    """
    Returns an instantiated adapter for the given engine key.
    Instantiation is done lazily to avoid abstract class issues.
    """
    try:
        adapter_cls = _ADAPTER_CLASSES[engine_key]
    except KeyError:
        raise ValueError(f"Unknown form engine: {engine_key}")

    return adapter_cls()


def get_all_adapters():
    """
    Returns all available adapters as instances.
    Used by unified form listing.
    """
    return [cls() for cls in _ADAPTER_CLASSES.values()]