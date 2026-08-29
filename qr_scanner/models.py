from django.db import models
from django.conf import settings
from django.utils import timezone


class QRScanSession(models.Model):
    """
    Records each QR scan verification attempt.
    Stores both scanned codes and whether they matched.
    """

    RESULT_PASS = "PASS"
    RESULT_FAIL = "FAIL"
    RESULT_CHOICES = [
        (RESULT_PASS, "Pass"),
        (RESULT_FAIL, "Fail"),
    ]

    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qr_scan_sessions",
        help_text="User who performed the scan",
    )

    qr_code_1 = models.CharField(
        max_length=1000,
        help_text="First QR code scanned",
    )

    qr_code_2 = models.CharField(
        max_length=1000,
        help_text="Second QR code scanned",
    )

    is_match = models.BooleanField(
        help_text="True if both QR codes matched (PASS), False otherwise (FAIL)",
        db_index=True,
    )

    result = models.CharField(
        max_length=10,
        choices=RESULT_CHOICES,
        db_index=True,
    )

    scanned_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    # Optional plant context (auto-resolved from user scope)
    plant = models.ForeignKey(
        "org.Plant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="qr_scan_sessions",
    )

    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-scanned_at"]
        verbose_name = "QR Scan Session"
        verbose_name_plural = "QR Scan Sessions"
        indexes = [
            models.Index(fields=["-scanned_at"]),
            models.Index(fields=["result", "-scanned_at"]),
            models.Index(fields=["scanned_by", "-scanned_at"]),
        ]

    def save(self, *args, **kwargs):
        # Keep result field in sync with is_match
        self.result = self.RESULT_PASS if self.is_match else self.RESULT_FAIL
        super().save(*args, **kwargs)

    def __str__(self):
        return f"QR Scan by {self.scanned_by} at {self.scanned_at:%Y-%m-%d %H:%M} — {self.result}"
