from django.views.generic import TemplateView

class ServiceWorkerView(TemplateView):
    template_name = "service_worker.js"
    content_type = "application/javascript"