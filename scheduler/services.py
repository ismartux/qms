from datetime import timedelta, datetime
from django.utils import timezone
from django.db import transaction

from .models import FormSchedule, ScheduledInstance, SchedulerControl
from submissions.models import Submission
from core.workflow.states import WorkflowState


THROTTLE_MINUTES = 5


# ============================================================
# MAIN ENTRY
# ============================================================

def run_scheduler():
    """
    Safe entry point (can be called from middleware).
    Throttled using SchedulerControl.
    """

    control, _ = SchedulerControl.objects.get_or_create(id=1)

    if not control.should_run(minutes=THROTTLE_MINUTES):
        return

    now = timezone.now()

    schedules = FormSchedule.objects.filter(is_active=True)

    for schedule in schedules:
        process_schedule(schedule, now)

    control.last_run = now
    control.save(update_fields=["last_run"])


def process_schedule(schedule, now):

    if schedule.schedule_type == "interval":
        process_interval(schedule, now)

    elif schedule.schedule_type == "shift_limit":
        process_shift_limit(schedule, now)

    elif schedule.schedule_type == "daily":
        process_daily(schedule, now)


# ============================================================
# INTERVAL
# ============================================================

def process_interval(schedule, now):

    interval = schedule.interval_minutes
    if not interval:
        return

    last_instance = schedule.instances.order_by("-expected_at").first()

    if last_instance:
        next_expected = last_instance.expected_at + timedelta(minutes=interval)
    else:
        next_expected = now

    if now >= next_expected:
        create_instance_and_submission(schedule, next_expected)


# ============================================================
# SHIFT LIMIT (simple daily counter logic)
# ============================================================

def process_shift_limit(schedule, now):

    limit = schedule.times_per_shift
    if not limit:
        return

    today = now.date()

    count = Submission.objects.filter(
        template_version__template=schedule.template,
        workflow_state=WorkflowState.SUBMITTED,
        created_at__date=today
    ).count()

    if count < limit:
        create_instance_and_submission(schedule, now)


# ============================================================
# DAILY
# ============================================================

def process_daily(schedule, now):

    if not schedule.daily_time:
        return

    today_datetime = datetime.combine(
        now.date(),
        schedule.daily_time
    )

    today_datetime = timezone.make_aware(today_datetime)

    already_created = schedule.instances.filter(
        expected_at__date=now.date()
    ).exists()

    if now >= today_datetime and not already_created:
        create_instance_and_submission(schedule, today_datetime)


# ============================================================
# CORE CREATION
# ============================================================

@transaction.atomic
def create_instance_and_submission(schedule, expected_at):

    existing_instance = ScheduledInstance.objects.filter(
        schedule=schedule,
        expected_at=expected_at
    ).first()

    if existing_instance:
        if not existing_instance.created_submission_id:
            ensure_submission(schedule, existing_instance)
        return

    instance = ScheduledInstance.objects.create(
        schedule=schedule,
        expected_at=expected_at,
        is_completed=False
    )

    ensure_submission(schedule, instance)


def ensure_submission(schedule, instance):

    template_version = (
        schedule.template.versions
        .filter(is_active=True)
        .order_by("-version_number")
        .first()
    )

    if not template_version:
        return

    # Prevent duplicate DRAFT for this template
    existing_submission = Submission.objects.filter(
        template_version=template_version,
        workflow_state=WorkflowState.DRAFT
    ).order_by("-created_at").first()

    if existing_submission:
        instance.created_submission_id = existing_submission.submission_id
        instance.save(update_fields=["created_submission_id"])
        return

    # Create new draft submission
    submission = Submission.objects.create(
        template_version=template_version,
        workflow_state=WorkflowState.DRAFT
    )

    instance.created_submission_id = submission.submission_id
    instance.save(update_fields=["created_submission_id"])


# ============================================================
# MARK INSTANCE COMPLETE
# ============================================================

def mark_instance_completed(submission):

    template = submission.template_version.template

    instance = ScheduledInstance.objects.filter(
        schedule__template=template,
        is_completed=False
    ).order_by("expected_at").first()

    if not instance:
        return

    instance.is_completed = True
    instance.created_submission_id = submission.submission_id
    instance.save(update_fields=["is_completed", "created_submission_id"])