from django.db.models import Q


def has_access(user, *, plant=None, department=None, section=None, roles=None):
    """
    Flexible scope-based access check.

    Parameters:
    - plant: Plant instance or ID
    - department: Department instance or ID
    - section: Section ID (if applicable)
    - roles: Iterable of role codes
    """

    if not user or not user.is_authenticated:
        return False

    # Superuser bypass
    if user.is_superuser:
        return True

    scopes = user.scopes.select_related("role")

    # Normalize IDs
    plant_id = getattr(plant, "id", plant)
    department_id = getattr(department, "id", department)

    filters = Q()

    if plant_id:
        filters &= Q(plant_id=plant_id)

    if department_id:
        filters &= Q(department_id=department_id)

    if roles:
        filters &= Q(role__code__in=roles)

    if section:
        # Only apply if section exists in UserScope model
        if hasattr(user.scopes.model, "section"):
            section_id = getattr(section, "id", section)
            filters &= Q(section_id=section_id)

    if filters:
        return scopes.filter(filters).exists()

    # If no filters provided → user has any scope
    return scopes.exists()