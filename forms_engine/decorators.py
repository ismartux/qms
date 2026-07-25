from django.http import HttpResponseForbidden
from functools import wraps

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return HttpResponseForbidden("Admin access required")
        return view_func(request, *args, **kwargs)
    return wrapper