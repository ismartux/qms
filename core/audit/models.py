from django.db import models
from django.conf import settings


# =====================================================
# AUDIT LOG
# =====================================================
class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True,
    )

    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=100, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["object_type", "object_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.object_type}:{self.object_id}"


# =====================================================
# DOMAIN EVENT
# =====================================================
class DomainEvent(models.Model):
    # Optional idempotency field (SAFE ADDITION)
    event_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="External event ID for idempotency"
    )

    event_type = models.CharField(max_length=50, db_index=True)
    object_type = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=64, db_index=True)

    payload = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_type"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type} on {self.object_type}:{self.object_id}"