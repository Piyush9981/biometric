import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

from outpass_app.models import outpass_request
from biometric.models import PendingBiometricVerification

logger = logging.getLogger('biometric.verification')

@receiver(post_save, sender=outpass_request)
def handle_request_approved(sender, instance, created, **kwargs):
    """
    1. Automatically creates a PendingBiometricVerification record when an
       outpass request is Approved.
    2. Resets the verification record to WAITING when the student is marked OUT.
    """
    if instance.request_status == 'Approved':
        # Check if already exists to prevent duplicate creation
        if not PendingBiometricVerification.objects.filter(request=instance).exists():
            now = timezone.now()
            expires = instance.requested_exit_datetime + timedelta(minutes=instance.late_grace or 0)

            PendingBiometricVerification.objects.create(
                request=instance,
                student=instance.student_id,  # student_id field in outpass_request is the FK to student_master
                approved_at=now,
                expires_at=expires,
                verification_status='WAITING'
            )
            logger.info(f"Signal: Created PendingBiometricVerification for Request {instance.request_id} (Expires at {expires}).")
    elif instance.request_status == 'OUT':
        affected = PendingBiometricVerification.objects.filter(request=instance).update(
            verification_status='OUT',
            verified_at=None,
            timed_out_at=None,
            attendance_log=None,
            remarks="Student marked OUT. Waiting for return scan."
        )
        if affected:
            logger.info(f"Signal: Reset PendingBiometricVerification to OUT for Request {instance.request_id} for return scan.")


@receiver(post_save, sender=PendingBiometricVerification)
def sync_request_status(sender, instance, **kwargs):
    """
    Syncs verification status ('ACCEPTED' or 'TIME_OUT') back to the outpass_request.
    """
    if instance.verification_status in ['ACCEPTED', 'TIME_OUT']:
        req = instance.request
        if req.request_status in ['IN', 'Decline', 'Reject', 'TIMEOUT_PROCESSED'] or (req.request_status in ['TIME_OUT', 'TIME OUT', 'Time out'] and req.terminated_at is not None):
            return

        status_map = {
            'ACCEPTED': 'ACCEPTED',
            'TIME_OUT': 'TIME OUT',
        }
        new_status = status_map.get(instance.verification_status)

        if new_status and req.request_status != new_status:
            req.request_status = new_status
            if new_status == 'ACCEPTED':
                req.accepted_at = instance.verified_at or timezone.now()
            req.save(update_fields=['request_status', 'accepted_at'])
            logger.info(f"Signal: Updated outpass_request {req.request_id} status to {new_status}.")
