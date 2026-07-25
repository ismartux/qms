# core/middleware/rbac.py

from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from core.identity.permissions import has_permission


class PermissionRequiredMixin(AccessMixin):
    """
    Mixin that verifies the user has the specified permission.
    """

    permission_required = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if not has_permission(request.user, self.permission_required):
            if self.raise_exception:
                raise PermissionDenied
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(AccessMixin):
    """
    OPTIONAL: Only use if you truly need strict role match.
    (Avoid for multi-role systems)
    """

    role_required = None

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        # --------------------------------------------------
        # 🔐 Plant-aware role filtering (SAFE)
        # --------------------------------------------------
        work_context = getattr(request.user, "active_work_context", None)

        if work_context:
            role_codes = request.user.scopes.filter(
                plant=work_context.plant
            ).values_list("role__code", flat=True)
        else:
            # Fallback (no active context)
            role_codes = request.user.scopes.values_list(
                "role__code",
                flat=True
            )

        if self.role_required not in role_codes:
            if self.raise_exception:
                raise PermissionDenied
            return redirect("login")

        return super().dispatch(request, *args, **kwargs)