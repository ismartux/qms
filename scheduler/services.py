from datetime import timedelta, datetime
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import FormSchedule, ScheduledInstance, SchedulerControl, MissedFormAlert
from submissions.models import Submission, WorkContext
from core.workflow.states import WorkflowState
from notifications.utils import get_lark_webhook
import requests
import json

User = get_user_model()


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

    # Get default values
    from org.models import Shop, Line, Product
    
    # Try to get a default shop, line, and plant
    default_line = None
    default_product = None
    default_plant = None
    
    # Get first available shop
    shop = Shop.objects.first()
    if shop:
        default_plant = shop.plant
        default_line = Line.objects.filter(shop=shop).first()
    
    if not default_line:
        default_line = Line.objects.first()

    if not default_line:
        # Cannot create submission without a Line
        return

    # Get first product if available
    default_product = Product.objects.first()
    
    # Get system user for automated submissions
    from django.contrib.auth import get_user_model
    User = get_user_model()
    system_user = User.objects.filter(is_superuser=True).first()
    
    if not system_user:
        # If no superuser exists, skip creating submission
        return

    # Create new draft submission with required fields
    submission = Submission.objects.create(
        template_version=template_version,
        workflow_state=WorkflowState.DRAFT,
        plant=default_plant,
        line=default_line,
        product=default_product,
        submitted_by=system_user,
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
    
    # Mark any missed alerts as resolved
    MissedFormAlert.objects.filter(
        instance=instance,
        notification_sent=False
    ).update(notification_sent=True)


# ============================================================
# MISSED FORM DETECTION & ALERTS
# ============================================================

def detect_and_alert_missed_forms():
    """
    Detect missed form submissions and send alerts.
    Should be called periodically (e.g., every 15 minutes).
    
    - Group alerts: Sent ONLY ONCE per form + user + business_date + shift (to avoid spam)
    - Personal notifications: Sent once per form + user + business_date + shift
    """
    now = timezone.now()
    
    # Find incomplete instances past due (within last 24 hours)
    recent_cutoff = now - timedelta(hours=24)
    missed_instances = ScheduledInstance.objects.filter(
        is_completed=False,
        expected_at__gte=recent_cutoff,
        expected_at__lte=now
    ).select_related(
        'schedule__template',
        'schedule'
    )
    
    for instance in missed_instances:
        template = instance.schedule.template
        
        # Get active work contexts for this schedule's template
        active_contexts = WorkContext.objects.filter(
            is_active=True,
            work_date=now.date()
        ).select_related('user', 'plant', 'shop', 'line', 'product')
        
        for context in active_contexts:
            user = context.user
            
            # Use get_or_create with business_date + shift for deduplication
            # This ensures only ONE alert per form + user + business_date + shift
            alert, created = MissedFormAlert.objects.get_or_create(
                template=template,
                user=user,
                business_date=context.work_date,
                shift=context.shift,
                defaults={
                    'instance': instance,
                    'expected_at': instance.expected_at,
                }
            )
            
            if created:
                # Always send personal notification
                send_missed_form_notification(alert, user, template, instance)
                
                # Send group alert ONLY ONCE per form + business_date + shift
                # Check if any alert already sent group alert for this combo
                group_already_sent = MissedFormAlert.objects.filter(
                    template=template,
                    business_date=context.work_date,
                    shift=context.shift,
                    group_alert_sent=True
                ).exists()
                
                if not group_already_sent:
                    # Send group alert
                    send_group_alert(alert, user, template, instance)
                    # Mark this alert as group_alert_sent
                    alert.group_alert_sent = True
                    alert.save(update_fields=['group_alert_sent'])


def send_upcoming_reminders():
    """
    Send reminders 15 minutes before scheduled form time.
    Only sends personal notifications (NOT group alerts).
    Should be called periodically (e.g., every 5 minutes).
    """
    now = timezone.now()
    reminder_time = now + timedelta(minutes=15)
    
    # Find instances due in the next 15 minutes
    upcoming_instances = ScheduledInstance.objects.filter(
        is_completed=False,
        expected_at__gt=now,
        expected_at__lte=reminder_time
    ).select_related(
        'schedule__template',
        'schedule'
    )
    
    for instance in upcoming_instances:
        template = instance.schedule.template
        
        # Get active work contexts
        active_contexts = WorkContext.objects.filter(
            is_active=True,
            work_date=now.date()
        ).select_related('user', 'plant', 'shop', 'line', 'product')
        
        for context in active_contexts:
            user = context.user
            
            # Check if reminder already sent (within last 20 minutes to avoid duplicates)
            recent_reminder = MissedFormAlert.objects.filter(
                instance=instance,
                user=user,
                created_at__gte=now - timedelta(minutes=20)
            ).exists()
            
            if not recent_reminder:
                # Create a reminder alert (notification_sent=True means reminder sent)
                alert = MissedFormAlert.objects.create(
                    instance=instance,
                    user=user,
                    template=template,
                    expected_at=instance.expected_at,
                    notification_sent=True  # Mark as sent since this is a notification
                )
                
                # Send reminder notification
                send_form_reminder(alert, user, template, instance)


def send_form_reminder(alert, user, template, instance):
    """
    Send reminder notification 15 minutes before scheduled time
    """
    try:
        from notifications.models import Notification
        
        message = (
            f"⏰ Form Submission Reminder\n\n"
            f"Form: {template.name}\n"
            f"Scheduled Time: {instance.expected_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Time Remaining: 15 minutes\n\n"
            f"Please complete this form on time."
        )
        
        # Try to use EHSNotification model if available
        try:
            from ehs_engine.models import EHSNotification
            EHSNotification.objects.create(
                recipient=user,
                title=f"Reminder: {template.name} due in 15 minutes",
                message=message,
                is_read=False
            )
        except ImportError:
            # Fallback: Log the notification
            print(f"[FORM REMINDER] User: {user.get_full_name()}, Form: {template.name}, Time: {instance.expected_at}")
        
    except Exception as e:
        print(f"Error sending reminder: {str(e)}")


def send_missed_form_notification(alert, user, template, instance):
    """
    Send in-app notification to the user
    """
    try:
        from notifications.models import Notification  # Adjust import based on your notification model
        
        # Create in-app notification
        # Adjust this based on your actual notification system
        message = (
            f"⚠️ Missed Form Alert\n\n"
            f"Form: {template.name}\n"
            f"Expected Time: {instance.expected_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Status: Not submitted\n\n"
            f"Please complete this form immediately."
        )
        
        # Try to use EHSNotification model if available
        try:
            from ehs_engine.models import EHSNotification
            EHSNotification.objects.create(
                recipient=user,
                title=f"Missed Form: {template.name}",
                message=message,
                is_read=False
            )
        except ImportError:
            # Fallback: Log the notification
            print(f"[MISSED FORM ALERT] User: {user.get_full_name()}, Form: {template.name}, Time: {instance.expected_at}")
        
        # Mark as sent
        alert.notification_sent = True
        alert.save(update_fields=['notification_sent'])
        
    except Exception as e:
        print(f"Error sending notification: {str(e)}")


def send_group_alert(alert, user, template, instance):
    """
    Send alert to Lark group chat
    """
    try:
        # Get Lark webhook URL for missed forms
        webhook_url = get_lark_webhook("missed_form")
        
        if not webhook_url:
            # Try generic alert webhook
            webhook_url = get_lark_webhook("alert")
        
        if not webhook_url:
            print(f"[LARK ALERT] No webhook configured for missed forms")
            return
        
        # Prepare message
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "⚠️ Missed Form Alert"
                    },
                    "template": "red"
                },
                "elements": [
                    {
                        "tag": "div",
                        "fields": [
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**User:** {user.get_full_name()}"
                                }
                            },
                            {
                                "is_short": True,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**User ID:** {user.id}"
                                }
                            },
                            {
                                "is_short": False,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**Form:** {template.name}"
                                }
                            },
                            {
                                "is_short": False,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**Expected Time:** {instance.expected_at.strftime('%Y-%m-%d %H:%M')}"
                                }
                            },
                            {
                                "is_short": False,
                                "text": {
                                    "tag": "lark_md",
                                    "content": f"**Status:** ❌ Not Submitted"
                                }
                            }
                        ]
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"Action Required: Please follow up with the user to complete the form."
                            }
                        ]
                    }
                ]
            }
        }
        
        # Send to Lark
        response = requests.post(
            webhook_url,
            json=message,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            alert.group_alert_sent = True
            alert.save(update_fields=['group_alert_sent'])
        else:
            print(f"[LARK ALERT ERROR] Status: {response.status_code}, Response: {response.text}")
            
    except Exception as e:
        print(f"Error sending group alert: {str(e)}")
