from django.core.management.base import BaseCommand
from biometric.services.sync import sync_all_logs

class Command(BaseCommand):
    help = 'Synchronize attendance logs from all registered biometric machines.'

    def handle(self, *args, **options):
        self.stdout.write('Starting biometric attendance sync...')
        try:
            total_synced = sync_all_logs()
            self.stdout.write(self.style.SUCCESS(f'Successfully synchronized {total_synced} logs.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Sync failed: {e}'))
