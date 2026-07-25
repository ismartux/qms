# core/management/commands/archive_submissions.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from core.services.archival import ArchivalService


class Command(BaseCommand):
    help = 'Archive old submissions and related data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=365,
            help='Archive submissions older than this many days (default: 365)'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Permanently delete archived submissions older than 3 years'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually doing it'
        )

    def handle(self, *args, **options):
        days = options['days']
        cleanup = options['cleanup']
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No actual changes will be made')
            )

        try:
            if cleanup:
                self.stdout.write(
                    'Cleaning up archived submissions older than 3 years...'
                )

                if not dry_run:
                    with transaction.atomic():
                        result = ArchivalService.cleanup_old_archived_submissions()

                    if result['status'] == 'success':
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully cleaned up {result['deleted_count']} submissions, "
                                f"{result['deleted_responses']} responses, "
                                f"and {result['deleted_capas']} CAPAs."
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"Cleanup failed: {result['message']}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            'Would clean up archived submissions older than 3 years'
                        )
                    )

            else:
                self.stdout.write(
                    f'Archiving submissions older than {days} days...'
                )

                if not dry_run:
                    with transaction.atomic():
                        result = ArchivalService.archive_old_submissions(days=days)

                    if result['status'] == 'success':
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Successfully archived {result['archived_count']} "
                                f"submissions and {result['archived_capas']} CAPAs."
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"Archival failed: {result['message']}")
                        )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Would archive submissions older than {days} days'
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error: {str(e)}")
            )