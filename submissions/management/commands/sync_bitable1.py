import os
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from submissions.models import SubmissionSyncLog
from integrations.bitable.service import sync_submission_chunk
from core.tenant.context import clear_current_plant


BATCH_LIMIT = 25


class Command(BaseCommand):
    help = "Sync pending submissions to Bitable (chunked & resumable)"

    def handle(self, *args, **kwargs):

        print("SYNC WORKER PID:", os.getpid())

        # -------------------------------------------------
        # IMPORTANT:
        # Ensure no tenant context interferes
        # -------------------------------------------------
        clear_current_plant()

        while True:

            with transaction.atomic():

                # -----------------------------------------
                # 🔒 LOCK ROWS TO PREVENT DOUBLE PROCESSING
                # -----------------------------------------
                logs_qs = (
                    SubmissionSyncLog.objects
                    .select_for_update(skip_locked=True)
                    .filter(
                        target="BITABLE",
                        status__in=["PENDING", "IN_PROGRESS"],
                    )
                    .order_by("last_attempt_at")[:BATCH_LIMIT]
                )

                logs = list(logs_qs)

                if not logs:
                    print("No pending submissions.")
                    return

                now = timezone.now()

                # Mark selected logs as IN_PROGRESS
                for log in logs:
                    log.status = "IN_PROGRESS"
                    log.attempts += 1
                    log.last_attempt_at = now

                SubmissionSyncLog.objects.bulk_update(
                    logs,
                    ["status", "attempts", "last_attempt_at"],
                )

            # -----------------------------------------
            # 🚀 PROCESS OUTSIDE LOCK TRANSACTION
            # -----------------------------------------
            for log in logs:

                try:
                    # Ensure submission is fully loaded
                    submission = log.submission

                    sync_submission_chunk(submission, log)

                except Exception as e:
                    # ---------------------------------
                    # ❌ FAILURE HANDLING
                    # ---------------------------------
                    SubmissionSyncLog.objects.filter(
                        pk=log.pk
                    ).update(
                        status="FAILED",
                        error=str(e),
                        last_attempt_at=timezone.now(),
                    )

            # Loop again to process next batch