from django.db.models import Count, Avg, Q
from django.utils import timezone
from capa.models import CAPA


class CAPAMetrics:

    @staticmethod
    def summary(plant=None):
        qs = CAPA.objects.all()

        if plant:
            qs = qs.filter(submission__plant=plant)

        return qs.aggregate(
            total=Count("pk"),
            open_count=Count(
                "pk",
                filter=Q(status__in=["OPEN", "ASSIGNED", "ACTION_DONE"])
            ),
            closed=Count(
                "pk",
                filter=Q(status="CLOSED")
            ),
            overdue=Count(
                "pk",
                filter=Q(
                    due_date__lt=timezone.now().date(),
                    status__in=["OPEN", "ASSIGNED"]
                )
            ),
            avg_severity=Avg("severity"),
        )

    @staticmethod
    def status_distribution(plant=None):
        qs = CAPA.objects.all()

        if plant:
            qs = qs.filter(submission__plant=plant)

        return qs.values("status").annotate(count=Count("pk"))
