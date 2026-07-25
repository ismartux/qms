from core.tenant.context import set_current_plant, clear_current_plant


class PlantIsolationMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        plant = None

        if request.user.is_authenticated:

            # Example: from active_work_context
            work_context = getattr(request.user, "active_work_context", None)

            if work_context:
                plant = work_context.plant

        set_current_plant(plant)

        response = self.get_response(request)

        clear_current_plant()

        return response