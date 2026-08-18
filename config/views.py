from django.views.generic import TemplateView


class OfflineView(TemplateView):
    template_name = "offline.html"
