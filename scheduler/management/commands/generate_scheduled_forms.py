from django.core.management.base import BaseCommand
from scheduler.services import run_scheduler


class Command(BaseCommand):
    help = "Manually trigger form scheduler"

    def handle(self, *args, **kwargs):
        run_scheduler()
        self.stdout.write(self.style.SUCCESS("Scheduler executed successfully."))