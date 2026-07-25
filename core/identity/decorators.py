from functools import wraps
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from .access import has_access


def access_required(**rules):
    """
    Decorator for enforcing scoped access control.

    Example:
        @access_required(plant=1, roles=["ADMIN"])
        def view(...):
            ...
    """

    def decorator(view):

        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):

            user = request.user

            # Superuser bypass
            if user.is_superuser:
                return view(request, *args, **kwargs)

            if not has_access(user, **rules):
                return HttpResponseForbidden("Access denied")

            return view(request, *args, **kwargs)

        return wrapper

    return decorator