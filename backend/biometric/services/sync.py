import logging
from django.utils import timezone
from biometric.models import Machine, SyncHistory
from biometric.services.attendance import download_new_logs
from biometric.services.users import sync_users_from_machine
from biometric.services.verification import match_pending_verifications

# Use dedicated sync logger
logger = logging.getLogger('biometric.sync')

def sync_all_logs():
    """
    Triggers attendance log synchronization for all active and enabled machines.
    Logs sync history in SyncHistory table.
    Returns the total number of synced logs.
    """
    logger.info("Synchronization Started")
    machines = Machine.objects.filter(machine_enabled=True)
    if not machines.exists():
        logger.info("No active/enabled machines configured for syncing attendance logs.")
        logger.info("Synchronization Finished")
        return 0

    total_synced = 0
    for machine in machines:
        try:
            logger.info(f"Starting attendance log sync for machine: {machine.machine_name}")
            count = download_new_logs(machine)
            
            if count > 0:
                SyncHistory.objects.create(
                    machine=machine,
                    sync_type='LOGS',
                    status='SUCCESS',
                    completed_at=timezone.now(),
                    total_records=count,
                    remarks=f"Successfully synchronized {count} logs."
                )
            
            total_synced += count
        except Exception as e:
            logger.error(f"Error during attendance log sync for machine {machine.machine_name}: {e}")

    # After downloading logs from all machines, run the bulk matching logic for pending requests
    try:
        matched_results = match_pending_verifications()
        logger.info(f"Bulk verification complete. Matched and updated {len(matched_results)} requests.")
    except Exception as e:
        logger.error(f"Failed to match pending verifications during bulk sync: {e}")

    logger.info("Synchronization Finished")
    return total_synced


def sync_all_users():
    """
    Triggers user synchronization for all active and enabled machines.
    Logs sync history in SyncHistory table.
    Returns the total number of synced users.
    """
    machines = Machine.objects.filter(machine_enabled=True)
    if not machines.exists():
        logger.info("No active/enabled machines configured for syncing users.")
        return 0

    total_synced = 0
    for machine in machines:
        try:
            logger.info(f"Starting user sync for machine: {machine.machine_name}")
            count = sync_users_from_machine(machine)
            
            if count > 0:
                SyncHistory.objects.create(
                    machine=machine,
                    sync_type='USERS',
                    status='SUCCESS',
                    completed_at=timezone.now(),
                    total_records=count,
                    remarks=f"Successfully synchronized {count} users from device."
                )
            
            total_synced += count
        except Exception as e:
            logger.error(f"Error during user sync for machine {machine.machine_name}: {e}")

    return total_synced
