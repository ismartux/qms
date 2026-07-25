import logging
from django.utils import timezone
from django.db import transaction
from submissions.models import Submission
from capa.models import CAPA

logger = logging.getLogger(__name__)


class ArchivalService:
    """
    Service for archiving old submissions and related data.
    """

    @staticmethod
    def archive_old_submissions(days=365):
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        submissions_to_archive = Submission.objects.filter(
            created_at__lt=cutoff_date,
            is_archived=False
        )

        count = submissions_to_archive.count()

        if count == 0:
            return {
                "status": "success",
                "message": "No submissions to archive.",
                "archived_count": 0,
            }

        logger.info(
            f"Starting archival of {count} submissions older than {cutoff_date}"
        )

        try:
            with transaction.atomic():

                archived_count = submissions_to_archive.update(is_archived=True)

                archived_capas = CAPA.objects.filter(
                    submission__created_at__lt=cutoff_date,
                    submission__is_archived=True,
                    is_archived=False,
                ).update(is_archived=True)

            logger.info(
                f"Successfully archived {archived_count} submissions "
                f"and {archived_capas} CAPAs"
            )

            return {
                "status": "success",
                "message": (
                    f"Successfully archived {archived_count} submissions "
                    f"and {archived_capas} CAPAs."
                ),
                "archived_count": archived_count,
                "archived_capas": archived_capas,
            }

        except Exception as e:
            logger.exception("Error during archival")
            return {
                "status": "error",
                "message": str(e),
                "archived_count": 0,
            }

    @staticmethod
    def cleanup_old_archived_submissions(days=1095):
        cutoff_date = timezone.now() - timezone.timedelta(days=days)

        submissions_to_delete = Submission.objects.filter(
            created_at__lt=cutoff_date,
            is_archived=True,
        )

        count = submissions_to_delete.count()

        if count == 0:
            return {
                "status": "success",
                "message": "No archived submissions to delete.",
                "deleted_count": 0,
            }

        logger.info(
            f"Starting cleanup of {count} archived submissions "
            f"older than {cutoff_date}"
        )

        try:
            with transaction.atomic():

                # Delete submissions (CASCADE handles responses + CAPA)
                deleted_count, _ = submissions_to_delete.delete()

            logger.info(
                f"Successfully deleted {deleted_count} archived submissions."
            )

            return {
                "status": "success",
                "message": (
                    f"Successfully deleted {deleted_count} archived submissions."
                ),
                "deleted_count": deleted_count,
            }

        except Exception as e:
            logger.exception("Error during cleanup")
            return {
                "status": "error",
                "message": str(e),
                "deleted_count": 0,
            }