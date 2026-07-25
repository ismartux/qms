from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from ui.admin_panel.permissions import is_admin


def admin_check(user):
    if not user.is_authenticated:
        return False
    if not is_admin(user):
        raise PermissionDenied("Admin access required")
    return True


admin_required = user_passes_test(
    admin_check,
    login_url="/login/",
)