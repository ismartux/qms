from .services import run_scheduler


class SchedulerMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        if request.user.is_authenticated:
            run_scheduler()

        response = self.get_response(request)
        return response