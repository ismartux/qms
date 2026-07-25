from datetime import datetime, timedelta, time
from django.utils import timezone


def get_operational_window():
    """
    Returns (start_datetime, end_datetime)
    Operational day = 08:00 AM → next day 08:00 AM
    """

    now = timezone.localtime()

    today_8am = timezone.make_aware(
        datetime.combine(now.date(), time(8, 0))
    )

    if now >= today_8am:
        start = today_8am
        end = start + timedelta(days=1)
    else:
        # before 8 AM → window started yesterday
        start = today_8am - timedelta(days=1)
        end = today_8am

    return start, end
