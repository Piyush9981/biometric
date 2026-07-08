import logging
from django.utils import timezone
from biometric.models import BiometricUser
from biometric.services.machine import MachineService

logger = logging.getLogger(__name__)

def sync_users_from_machine(machine):
    """
    Download users from the device and create/update BiometricUser records.
    """
    service = MachineService(machine)
    device_users = service.get_users()
    
    count = 0
    now = timezone.now()
    
    for du in device_users:
        card = du.card if hasattr(du, 'card') else ''
        if not card and hasattr(du, 'card_number'):
            card = du.card_number
            
        from outpass_app.models import student_master
        student_obj = student_master.objects.filter(student_id=str(du.user_id)).first()
        if not student_obj and str(du.user_id).startswith("sim_"):
            student_obj = student_master.objects.filter(student_id=str(du.user_id)[4:]).first()

        biometric_user, created = BiometricUser.objects.update_or_create(
            user_id=str(du.user_id),
            defaults={
                'student': student_obj,
                'machine_uid': du.uid,
                'name': du.name,
                'card_number': str(card) if card else '',
                'is_active': True,
                'last_sync': now,
            }
        )
        if created:
            logger.info(f"Downloaded new biometric user: {du.name} (ID: {du.user_id})")
        else:
            logger.info(f"Updated biometric user: {du.name} (ID: {du.user_id})")
        count += 1
        
    return count


def push_user_to_machine(machine, biometric_user):
    """
    Push a single local BiometricUser to the machine.
    """
    service = MachineService(machine)
    service.add_user(
        uid=biometric_user.machine_uid,
        name=biometric_user.name,
        privilege=0,  # Default to normal user
        password='',
        group_id='',
        user_id=biometric_user.user_id,
        card_number=biometric_user.card_number or 0
    )
    biometric_user.last_sync = timezone.now()
    biometric_user.save(update_fields=['last_sync'])
    logger.info(f"Pushed user {biometric_user.name} to machine {machine.machine_name}")


def delete_user_from_machine(machine, user_id):
    """
    Delete a user from the machine.
    """
    service = MachineService(machine)
    service.delete_user(user_id=user_id)
    logger.info(f"Deleted user {user_id} from machine {machine.machine_name}")
