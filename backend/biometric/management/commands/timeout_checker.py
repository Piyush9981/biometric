from django.core.management.base import BaseCommand
from biometric.services.verification import check_expired_verifications

class Command(BaseCommand):
    help = 'Check for expired biometric verification requests and mark them as TIMED OUT.'

    def handle(self, *args, **options):
        self.stdout.write('Checking for expired verification requests...')
        try:
            timed_out_count = check_expired_verifications()
            self.stdout.write(self.style.SUCCESS(f'Successfully timed out {timed_out_count} requests.'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Timeout checker failed: {e}'))
