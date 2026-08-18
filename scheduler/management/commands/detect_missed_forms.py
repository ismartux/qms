from django.core.management.base import BaseCommand
from scheduler.services import detect_and_alert_missed_forms


class Command(BaseCommand):
    help = 'Detect missed form submissions and send alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run detection without sending alerts',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting missed form detection...')
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No alerts will be sent'))
        
        try:
            detect_and_alert_missed_forms()
            self.stdout.write(
                self.style.SUCCESS('Missed form detection completed successfully')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during detection: {str(e)}')
            )