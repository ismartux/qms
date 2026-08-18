from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from forms_engine.models import ChecklistTemplate
from django.contrib.auth import get_user_model

User = get_user_model()


class FormSchedule(models.Model):

    SCHEDULE_TYPE = (
        ("interval", "Interval Based"),
        ("shift_limit", "Times Per Shift"),
        ("daily", "Daily"),
    )

    template = models.OneToOneField(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="schedule"
    )

    schedule_type = models.CharField(
        max_length=20,
        choices=SCHEDULE_TYPE
    )

    # Used when schedule_type = interval
    interval_minutes = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # Used when schedule_type = shift_limit
    times_per_shift = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    # Used when schedule_type = daily
    daily_time = models.TimeField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def clean(self):
        """
        Enforce correct configuration depending on schedule_type
        """

        if self.schedule_type == "interval":
            if not self.interval_minutes:
                raise ValidationError("Interval minutes is required for interval schedule.")
            self.times_per_shift = None
            self.daily_time = None

        elif self.schedule_type == "shift_limit":
            if not self.times_per_shift:
                raise ValidationError("Times per shift is required for shift_limit schedule.")
            self.interval_minutes = None
            self.daily_time = None

        elif self.schedule_type == "daily":
            if not self.daily_time:
                raise ValidationError("Daily time is required for daily schedule.")
            self.interval_minutes = None
            self.times_per_shift = None

    def save(self, *args, **kwargs):
        self.full_clean()  # ensures validation always runs
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.template.name} - {self.schedule_type}"
    
    
class ScheduledInstance(models.Model):

    schedule = models.ForeignKey(
        FormSchedule,
        on_delete=models.CASCADE,
        related_name="instances"
    )

    expected_at = models.DateTimeField()

    is_completed = models.BooleanField(default=False)

    created_submission_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expected_at"]
        indexes = [
            models.Index(fields=["expected_at"]),
            models.Index(fields=["is_completed"]),
        ]

    def __str__(self):
        return f"{self.schedule.template.name} @ {self.expected_at}"
    
    def is_missed(self):
        """Check if this instance was missed (past due and not completed)"""
        if self.is_completed:
            return False
        return timezone.now() > self.expected_at
    
    
class SchedulerControl(models.Model):

    last_run = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Scheduler Control"
        verbose_name_plural = "Scheduler Control"

    def should_run(self, minutes=5):
        if not self.last_run:
            return True
        return (timezone.now() - self.last_run).total_seconds() > minutes * 60

    def __str__(self):
        return "Scheduler Control"


class MissedFormAlert(models.Model):
    """Track missed form submissions and alert status"""
    
    instance = models.ForeignKey(
        ScheduledInstance,
        on_delete=models.CASCADE,
        related_name="missed_alerts"
    )
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="missed_form_alerts"
    )
    
    template = models.ForeignKey(
        ChecklistTemplate,
        on_delete=models.CASCADE,
        related_name="missed_alerts"
    )
    
    expected_at = models.DateTimeField()
    
    # Business context for deduplication
    business_date = models.DateField(
        null=True, blank=True, db_index=True,
        help_text="Business date (work_date) for deduplication"
    )
    shift = models.CharField(
        max_length=10, null=True, blank=True, db_index=True,
        help_text="Shift (DAY/NIGHT) for deduplication"
    )
    
    # Alert status
    notification_sent = models.BooleanField(default=False)
    group_alert_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "notification_sent"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["template", "user", "business_date", "shift"], name="idx_alert_dedup"),
        ]
        unique_together = ["template", "user", "business_date", "shift"]
    
    def __str__(self):
        return f"Missed: {self.user.get_full_name()} - {self.template.name} @ {self.expected_at}"
