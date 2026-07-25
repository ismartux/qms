from django.contrib.auth.decorators import user_passes_test
from ui.admin_panel.permissions import is_admin

admin_required = user_passes_test(
    is_admin,
    login_url="/login/"
)
