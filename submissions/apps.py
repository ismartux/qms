# submissions/apps.py

from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "submissions"

    def ready(self):
        # ❌ No background workers
        # ❌ No sync loops
        # ❌ No threads
        # ❌ No polling
        # ❌ No SubmissionSyncLog
        # ❌ No Bitable sync here
        pass
