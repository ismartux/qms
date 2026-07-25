# ui/form_runtime/registry.py

from ui.form_runtime.resolver import resolve_adapter


# =====================================================
# REGISTERED FORM ENGINES
# =====================================================
# Order matters:
# - Used for forms_list display order
# - Used by unified runtime
# =====================================================
ENGINE_KEYS = [
    "CHECKLIST",
    "DYNAMIC",
]


# =====================================================
# ALL ADAPTERS (FOR FORMS LIST)
# =====================================================
def get_all_adapters():
    """
    Returns all registered form runtime adapters.

    Used by:
    - forms_list_view

    Each adapter is responsible for:
    - visibility rules
    - role filtering
    - publish / active filtering
    """
    return [resolve_adapter(key) for key in ENGINE_KEYS]


# =====================================================
# SINGLE ADAPTER (FOR RUNTIME)
# =====================================================
def get_adapter(engine_key: str):
    """
    Return a single adapter by engine key.

    Used by:
    - unified_form_runtime_view

    Raises:
    - KeyError / ImproperlyConfigured via resolver
      if engine key is invalid
    """
    return resolve_adapter(engine_key)