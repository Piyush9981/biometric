import logging
from django.utils import timezone
from biometric.models import AttendanceLog, BiometricUser
from biometric.services.machine import MachineService

# Use dedicated attendance logger
logger = logging.getLogger('biometric.attendance')

def download_new_logs(machine):
    """
    Connects to the biometric device, retrieves attendance records, 
    filters and stores only the new logs, and maps them to student IDs.
    Does NOT trigger verification matching directly; matching is handled in the verification layer.
    Returns the number of new logs processed.
    """
    # Check if the machine is enabled
    if not machine.machine_enabled:
        logger.info(f"Skipping sync: Machine {machine.machine_name} is disabled.")
        return 0

    # 1. Connect to machine and fetch attendance logs
    service = MachineService(machine)
    try:
        raw_logs = service.get_attendance()
        logger.info(f"Attendance Downloaded: {len(raw_logs)} logs fetched from machine.")
    except Exception as e:
        logger.error(f"Failed to fetch attendance logs for machine {machine.id}: {e}")
        raise

    if not raw_logs:
        logger.info(f"No logs returned from machine {machine.machine_name}.")
        # Update last successful sync even if 0 logs returned
        machine.last_successful_sync = timezone.now()
        machine.save(update_fields=['last_successful_sync'])
        return 0

    # 2. Determine the threshold timestamp for new logs
    last_db_log = AttendanceLog.objects.filter(machine=machine).order_by('-attendance_time').first()
    
    threshold = None
    if last_db_log:
        threshold = last_db_log.attendance_time
    elif machine.last_attendance_time:
        threshold = machine.last_attendance_time

    # 3. Filter and save new logs
    new_logs_count = 0
    latest_processed_time = threshold

    # Sort raw logs by timestamp ascending to ensure chronological order
    raw_logs = sorted(raw_logs, key=lambda x: x.timestamp)

    for log in raw_logs:
        # Convert naive datetime from pyzk to aware datetime
        log_time = log.timestamp
        if timezone.is_naive(log_time):
            import zoneinfo
            kolkata_tz = zoneinfo.ZoneInfo('Asia/Kolkata')
            log_time = timezone.make_aware(log_time, timezone=kolkata_tz).astimezone(zoneinfo.ZoneInfo('UTC'))

        # Skip logs that are at or before our threshold
        if threshold and log_time <= threshold:
            continue

        # Look up student mapping via stable user_id instead of machine_uid
        student_obj = None
        user_mapping = BiometricUser.objects.filter(user_id=str(log.user_id)).first()
        if user_mapping and user_mapping.student:
            student_obj = user_mapping.student
        else:
            # Fallback direct lookup of student from student_master
            from outpass_app.models import student_master
            student_obj = student_master.objects.filter(student_id=str(log.user_id)).first()
            if not student_obj and str(log.user_id).startswith("sim_"):
                student_obj = student_master.objects.filter(student_id=str(log.user_id)[4:]).first()
            
            # Cache the mapping on the biometric user if found
            if user_mapping and student_obj:
                user_mapping.student = student_obj
                user_mapping.save(update_fields=['student'])
                
        if not student_obj:
            logger.warning(f"Attendance Skipped: Skipped attendance. Machine User ID: {log.user_id}. Reason: No BiometricUser mapping found.")
            if log_time and (latest_processed_time is None or log_time > latest_processed_time):
                latest_processed_time = log_time
            continue

        # Avoid duplicates using get_or_create
        attendance_log, created = AttendanceLog.objects.get_or_create(
            machine=machine,
            machine_uid=log.uid,
            attendance_time=log_time,
            defaults={
                'student': student_obj,
                'verify_type': log.status if hasattr(log, 'status') else 0,
                'processed': False
            }
        )

        if created:
            new_logs_count += 1
            if log_time and (latest_processed_time is None or log_time > latest_processed_time):
                latest_processed_time = log_time
            logger.info(f"Attendance Saved: Log {attendance_log.id} for student {student_obj.student_id} saved.")

    # 4. Update the machine's last attendance time and last successful sync
    machine.last_successful_sync = timezone.now()
    if latest_processed_time:
        machine.last_attendance_time = latest_processed_time
        machine.save(update_fields=['last_attendance_time', 'last_successful_sync'])
    else:
        machine.save(update_fields=['last_successful_sync'])

    logger.info(f"Successfully downloaded {new_logs_count} new logs from machine {machine.machine_name}.")
    return new_logs_count
