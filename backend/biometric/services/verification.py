import logging
from django.utils import timezone
from biometric.models import PendingBiometricVerification, AttendanceLog, Machine
from biometric.services.attendance import download_new_logs
from biometric.services.machine import MachineConnectionError
from datetime import timedelta

# Use dedicated verification logger
logger = logging.getLogger('biometric.verification')

def get_actual_utc_time(log):
    """
    Determines the actual UTC time represented by log.attendance_time
    by comparing possible UTC times with log.created_at.
    We simply pick the candidate that is closer in absolute time to log.created_at.
    Since machine local naive time was saved as UTC, shifting it by +5h 30m,
    we subtract 5h 30m to get the actual UTC time for real machine logs.
    For mock/test logs, the raw UTC time is already correct.
    """
    t1 = log.attendance_time
    t2 = log.attendance_time - timedelta(hours=5, minutes=30)
    
    ref = log.created_at or timezone.now()
    
    return min([t1, t2], key=lambda x: abs(x - ref))


def _build_result(request_instance):
    """Helper to format the verification result dictionary."""
    res = {
        "request_id": request_instance.request_id,
        "student_id": request_instance.student_id,
        "verification_status": request_instance.verification_status,
    }
    if request_instance.verification_status in ['ACCEPTED', 'READY_FOR_OUT', 'IN', 'READY_FOR_IN'] and request_instance.attendance_log:
        res["attendance_time"] = request_instance.attendance_log.attendance_time.isoformat()
    return res


def verify_single_request(request_id):
    """
    Core service to verify a single outpass request against biometric logs.
    
    1. Fetches PendingBiometricVerification.
    2. If status is ACCEPTED or TIME_OUT, returns the cached result.
    3. If WAITING or FAILED, triggers log sync from all active machines.
    4. If connection fails, marks the request status as FAILED.
    5. If sync succeeds, looks for a valid scan.
    6. Returns the structured result dictionary.
    """
    try:
        request = PendingBiometricVerification.objects.get(request_id=request_id)
    except PendingBiometricVerification.DoesNotExist:
        from outpass_app.models import outpass_request
        try:
            outpass_req = outpass_request.objects.get(request_id=request_id)
            from django.conf import settings
            expiry_minutes = getattr(settings, 'BIOMETRIC_EXPIRY_MINUTES', 30)
            now = timezone.now()
            expires = now + timedelta(minutes=expiry_minutes)
            request = PendingBiometricVerification.objects.create(
                request=outpass_req,
                student=outpass_req.student_id,
                approved_at=outpass_req.accepted_at or now,
                expires_at=expires,
                verification_status='OUT' if outpass_req.request_status == 'OUT' else 'WAITING'
            )
            logger.info(f"Dynamically created PendingBiometricVerification for Request {request_id}")
        except outpass_request.DoesNotExist:
            logger.error(f"Verification request {request_id} not found in pending database and outpass_request does not exist.")
            return None

    # Return cached result if already completed
    if request.verification_status in ['ACCEPTED', 'READY_FOR_OUT', 'TIME_OUT', 'READY_FOR_IN', 'IN']:
        logger.info(f"Returning cached result for Request {request_id}: {request.verification_status}")
        return _build_result(request)

    # Trigger log sync from enabled machines
    enabled_machines = Machine.objects.filter(machine_enabled=True)
    if not enabled_machines.exists():
        logger.warning(f"No enabled machines found to verify Request {request_id}.")
        return _build_result(request)

    sync_failed = False
    sync_remarks = []

    for machine in enabled_machines:
        try:
            download_new_logs(machine)
        except (MachineConnectionError, Exception) as e:
            logger.error(f"Sync failed for machine {machine.machine_name} during verify: {e}")
            sync_failed = True
            sync_remarks.append(f"Machine {machine.machine_name}: {str(e)}")

    if sync_failed:
        request.verification_status = 'FAILED'
        request.remarks = f"Verification failed due to connectivity errors: {'; '.join(sync_remarks)}"
        request.save(update_fields=['verification_status', 'remarks'])
        logger.error(f"Request {request_id} status set to FAILED.")
        return _build_result(request)

    # Sync succeeded. Search for a matching scan
    request.refresh_from_db()
    if request.verification_status in ['ACCEPTED', 'READY_FOR_OUT', 'TIME_OUT', 'READY_FOR_IN', 'IN']:
        logger.info(f"Returning updated status for Request {request_id}: {request.verification_status}")
        return _build_result(request)

    outpass_req = request.request
    outpass_req.refresh_from_db()
    
    if outpass_req.actual_exit_datetime is None:
        # --- OUT (EXIT) VERIFICATION WORKFLOW ---
        early_grace = 15 if (outpass_req.early_grace is None or outpass_req.early_grace == 0) else outpass_req.early_grace
        late_grace = 0 if outpass_req.late_grace is None else outpass_req.late_grace
        
        if getattr(outpass_req, 'recovery_attempts', 0) > 0 and outpass_req.recovery_started_at:
            earliest_allowed = outpass_req.recovery_started_at - timedelta(minutes=early_grace)
            latest_allowed = request.expires_at
            start_time = outpass_req.recovery_started_at
        else:
            start_time = outpass_req.requested_exit_datetime
            earliest_allowed = start_time - timedelta(minutes=early_grace)
            latest_allowed = start_time + timedelta(minutes=late_grace)

        logger.info(f"Verification parameters for Request {request_id}:")
        logger.info(f"  Student ID: {request.student_id}")
        logger.info(f"  Approved At: {request.approved_at}")
        logger.info(f"  Expires At: {request.expires_at}")
        logger.info(f"  Requested Exit: {start_time}")
        logger.info(f"  Allowed Window: {earliest_allowed} to {latest_allowed}")

        # Fetch ALL logs for this student to trace and check reasons
        logs = AttendanceLog.objects.filter(
            student_id=request.student_id
        ).order_by('attendance_time')

        logger.info(f"Total AttendanceLogs found for student {request.student_id}: {logs.count()}")

        matched_log = None
        matched_time = None

        for log in logs:
            actual_time = get_actual_utc_time(log)
            logger.info(f"Checking AttendanceLog ID {log.id}: time={log.attendance_time}, determined_actual_utc={actual_time}, processed={log.processed}")
            
            if log.processed:
                logger.info(f"  Attendance rejected for Request {request_id}. Reason: processed=True")
                continue

            rejection_reasons = []
            
            min_allowed_time = outpass_req.recovery_started_at if (getattr(outpass_req, 'recovery_attempts', 0) > 0 and outpass_req.recovery_started_at) else request.approved_at
            
            if actual_time < min_allowed_time - timedelta(seconds=5):
                rejection_reasons.append(f"attendance_time {actual_time} < approval/recovery time {min_allowed_time}")
            if actual_time > request.expires_at:
                rejection_reasons.append(f"attendance_time {actual_time} > expires_at {request.expires_at}")
            if actual_time < earliest_allowed:
                rejection_reasons.append(f"attendance_time {actual_time} < earliest_allowed {earliest_allowed}")
            if actual_time > latest_allowed:
                rejection_reasons.append(f"attendance_time {actual_time} > latest_allowed {latest_allowed}")

            if not rejection_reasons:
                matched_log = log
                matched_time = actual_time
                logger.info(f"  Matched successfully!")
                break
            else:
                logger.info(f"  Attendance log rejected. Reasons: {'; '.join(rejection_reasons)}")

        if matched_log:
            logger.info(f"Saving PendingBiometricVerification status to READY_FOR_OUT for Request {request.request_id}")
            request.verification_status = 'READY_FOR_OUT'
            request.verified_at = matched_time
            request.attendance_log = matched_log
            request.remarks = f"Exit scan verified successfully at {matched_time}."
            request.save(update_fields=['verification_status', 'verified_at', 'attendance_log', 'remarks'])

            logger.info(f"Saving AttendanceLog as processed for Log ID {matched_log.id}")
            matched_log.processed = True
            matched_log.save(update_fields=['processed'])

            outpass_req.refresh_from_db()
            logger.info(f"Current outpass_request status after saving PV: {outpass_req.request_status}")

            logger.info(f"Request {request_id} exit scan READY_FOR_OUT.")
            return _build_result(request)

        # No scan found yet. Check if request has expired in the meantime
        if timezone.now() > request.expires_at or timezone.now() > latest_allowed:
            logger.info(f"Request ID {request.request_id} expired. now ({timezone.now()}) > expires_at ({request.expires_at}) or latest_allowed ({latest_allowed})")
            request.verification_status = 'TIME_OUT'
            request.timed_out_at = timezone.now()
            request.remarks = f"Request exit window expired. No scan was registered within the allowed window."
            request.save(update_fields=['verification_status', 'timed_out_at', 'remarks'])
            
            outpass_req.refresh_from_db()
            logger.info(f"Current outpass_request status after timeout: {outpass_req.request_status}")
            
            logger.info(f"Request {request_id} exit scan TIMED OUT due to validity expiry.")
            return _build_result(request)

    else:
        # --- IN (RETURN) VERIFICATION WORKFLOW ---
        exit_time = outpass_req.actual_exit_datetime or request.approved_at or timezone.now()
        min_return_time = exit_time + timedelta(minutes=2)

        logger.info(f"Verification parameters for Return Request {request_id}:")
        logger.info(f"  Student ID: {request.student_id}")
        logger.info(f"  Exit Time: {exit_time}")
        logger.info(f"  Min Return Time: {min_return_time}")

        # Mark all unprocessed logs for this student that are older than min_return_time as processed
        unprocessed_logs = AttendanceLog.objects.filter(
            student_id=request.student_id,
            processed=False
        )
        for slog in unprocessed_logs:
            actual_time = get_actual_utc_time(slog)
            if actual_time < min_return_time:
                slog.processed = True
                slog.save(update_fields=['processed'])
                logger.info(f"Marked stale/exit scan log {slog.id} for student {request.student_id} as processed.")

        logs = AttendanceLog.objects.filter(
            student_id=request.student_id
        ).order_by('attendance_time')

        matched_log = None
        matched_time = None

        for log in logs:
            actual_time = get_actual_utc_time(log)
            logger.info(f"Checking Return AttendanceLog ID {log.id}: time={log.attendance_time}, determined_actual_utc={actual_time}, processed={log.processed}")
            
            if log.processed:
                logger.info(f"  Attendance rejected for Request {request_id}. Reason: processed=True")
                continue


            rejection_reasons = []
            if actual_time < min_return_time:
                rejection_reasons.append(f"attendance_time {actual_time} < min_return_time {min_return_time}")

            if not rejection_reasons:
                matched_log = log
                matched_time = actual_time
                logger.info(f"  Matched return successfully!")
                break
            else:
                logger.info(f"  Attendance log rejected. Reasons: {'; '.join(rejection_reasons)}")

        if matched_log:
            logger.info(f"Saving PendingBiometricVerification status to READY_FOR_IN for Request {request.request_id}")
            request.verification_status = 'READY_FOR_IN'
            request.verified_at = matched_time
            request.attendance_log = matched_log
            request.remarks = f"Return scan verified successfully at {matched_time}."
            request.save(update_fields=['verification_status', 'verified_at', 'attendance_log', 'remarks'])

            logger.info(f"Saving AttendanceLog as processed for Log ID {matched_log.id}")
            matched_log.processed = True
            matched_log.save(update_fields=['processed'])

            outpass_req.refresh_from_db()
            logger.info(f"Current outpass_request status after saving PV: {outpass_req.request_status}")

            logger.info(f"Request {request_id} return scan READY_FOR_IN.")
            return _build_result(request)

    # If it was previously FAILED but sync now succeeded, reset back to WAITING
    if request.verification_status == 'FAILED':
        request.verification_status = 'WAITING'
        request.remarks = "Sync retried successfully. Waiting for scan."
        request.save(update_fields=['verification_status', 'remarks'])

    logger.info(f"Request {request_id} remains WAITING for scan.")
    return _build_result(request)


def match_pending_verifications():
    """
    Bulk match WAITING or FAILED verifications against downloaded logs.
    Does NOT connect to the device. Used in cron/periodic background jobs.
    """
    logger.info("Verification Started")
    pending = PendingBiometricVerification.objects.filter(
        verification_status__in=['WAITING', 'FAILED', 'OUT']
    ).order_by('approved_at')

    results = []
    
    logger.info(f"match_pending_verifications executed. Found {pending.count()} pending verification records.")

    for request in pending:
        outpass_req = request.request
        outpass_req.refresh_from_db()
        
        if outpass_req.request_status not in ['Approved', 'OUT', 'TIME_OUT']:
            logger.info(f"Request ID {request.request_id} skipped from bulk match: request_status not Approved/OUT/TIME_OUT ({outpass_req.request_status})")
            continue
        
        if outpass_req.actual_exit_datetime is None:
            # --- OUT (EXIT) VERIFICATION WORKFLOW ---
            early_grace = 15 if (outpass_req.early_grace is None or outpass_req.early_grace == 0) else outpass_req.early_grace
            late_grace = 0 if outpass_req.late_grace is None else outpass_req.late_grace
            
            if getattr(outpass_req, 'recovery_attempts', 0) > 0 and outpass_req.recovery_started_at:
                earliest_allowed = outpass_req.recovery_started_at - timedelta(minutes=early_grace)
                latest_allowed = request.expires_at
                start_time = outpass_req.recovery_started_at
            else:
                start_time = outpass_req.requested_exit_datetime
                earliest_allowed = start_time - timedelta(minutes=early_grace)
                latest_allowed = start_time + timedelta(minutes=late_grace)

            logger.info(f"Bulk match checking WAITING Request ID {request.request_id}:")
            logger.info(f"  Student ID: {request.student_id}")
            logger.info(f"  Approved At: {request.approved_at}")
            logger.info(f"  Expires At: {request.expires_at}")
            logger.info(f"  Allowed Window: {earliest_allowed} to {latest_allowed}")

            logs = AttendanceLog.objects.filter(
                student_id=request.student_id
            ).order_by('attendance_time')

            logger.info(f"Total AttendanceLogs found for student {request.student_id}: {logs.count()}")

            matched_log = None
            matched_time = None

            for log in logs:
                actual_time = get_actual_utc_time(log)
                logger.info(f"Checking AttendanceLog ID {log.id}: time={log.attendance_time}, determined_actual_utc={actual_time}, processed={log.processed}")
                
                if log.processed:
                    logger.info(f"  Attendance rejected for Request {request.request_id}. Reason: processed=True")
                    continue

                rejection_reasons = []
                
                min_allowed_time = outpass_req.recovery_started_at if (getattr(outpass_req, 'recovery_attempts', 0) > 0 and outpass_req.recovery_started_at) else request.approved_at
                
                if actual_time < min_allowed_time - timedelta(seconds=5):
                    rejection_reasons.append(f"attendance_time {actual_time} < approval/recovery time {min_allowed_time}")
                if actual_time > request.expires_at:
                    rejection_reasons.append(f"attendance_time {actual_time} > expires_at {request.expires_at}")
                if actual_time < earliest_allowed:
                    rejection_reasons.append(f"attendance_time {actual_time} < earliest_allowed {earliest_allowed}")
                if actual_time > latest_allowed:
                    rejection_reasons.append(f"attendance_time {actual_time} > latest_allowed {latest_allowed}")

                if not rejection_reasons:
                    matched_log = log
                    matched_time = actual_time
                    logger.info(f"  Matched successfully!")
                    break
                else:
                    logger.info(f"  Attendance log rejected. Reasons: {'; '.join(rejection_reasons)}")

            if matched_log:
                logger.info(f"Verification Successful: Request ID {request.request_id} verification status updated to READY_FOR_OUT.")
                logger.info(f"Saving PendingBiometricVerification status to READY_FOR_OUT for Request {request.request_id}")
                request.verification_status = 'READY_FOR_OUT'
                request.verified_at = matched_time
                request.attendance_log = matched_log
                request.remarks = f"Bulk match: exit scan verified successfully at {matched_time}."
                request.save(update_fields=['verification_status', 'verified_at', 'attendance_log', 'remarks'])

                logger.info(f"Saving AttendanceLog as processed for Log ID {matched_log.id}")
                matched_log.processed = True
                matched_log.save(update_fields=['processed'])

                outpass_req.refresh_from_db()
                logger.info(f"Current outpass_request status after saving PV: {outpass_req.request_status}")

                results.append(_build_result(request))
            else:
                logger.info(f"Verification Failed: Request ID {request.request_id} remained WAITING.")
                # No scan found yet. Check if request has expired in the meantime
                if timezone.now() > request.expires_at:
                    logger.info(f"Request ID {request.request_id} expired. now ({timezone.now()}) > expires_at ({request.expires_at})")
                    logger.info(f"Timeout Executed: Request ID {request.request_id} transitioned to TIME_OUT.")
                    request.verification_status = 'TIME_OUT'
                    request.timed_out_at = timezone.now()
                    request.remarks = f"Bulk match: request exit window expired."
                    request.save(update_fields=['verification_status', 'timed_out_at', 'remarks'])
                    
                    outpass_req.refresh_from_db()
                    logger.info(f"Current outpass_request status after bulk timeout: {outpass_req.request_status}")
                    results.append(_build_result(request))
        else:
            # --- IN (RETURN) VERIFICATION WORKFLOW ---
            exit_time = outpass_req.actual_exit_datetime or request.approved_at or timezone.now()
            min_return_time = exit_time + timedelta(minutes=2)

            logger.info(f"Bulk match checking return Request ID {request.request_id}:")
            logger.info(f"  Student ID: {request.student_id}")
            logger.info(f"  Exit Time: {exit_time}")
            logger.info(f"  Min Return Time: {min_return_time}")

            unprocessed_logs = AttendanceLog.objects.filter(
                student_id=request.student_id,
                processed=False
            )
            for slog in unprocessed_logs:
                actual_time = get_actual_utc_time(slog)
                if actual_time < min_return_time:
                    slog.processed = True
                    slog.save(update_fields=['processed'])
                    logger.info(f"Bulk match: Marked stale/exit scan log {slog.id} for student {request.student_id} as processed.")

            logs = AttendanceLog.objects.filter(
                student_id=request.student_id
            ).order_by('attendance_time')

            matched_log = None
            matched_time = None

            for log in logs:
                actual_time = get_actual_utc_time(log)
                logger.info(f"Checking Return AttendanceLog ID {log.id}: time={log.attendance_time}, determined_actual_utc={actual_time}, processed={log.processed}")
                
                if log.processed:
                    logger.info(f"  Attendance rejected for Request {request.request_id}. Reason: processed=True")
                    continue


                rejection_reasons = []
                if actual_time < min_return_time:
                    rejection_reasons.append(f"attendance_time {actual_time} < min_return_time {min_return_time}")

                if not rejection_reasons:
                    matched_log = log
                    matched_time = actual_time
                    logger.info(f"  Matched return successfully!")
                    break
                else:
                    logger.info(f"  Attendance log rejected. Reasons: {'; '.join(rejection_reasons)}")

            if matched_log:
                logger.info(f"Saving PendingBiometricVerification status to READY_FOR_IN for Request {request.request_id}")
                request.verification_status = 'READY_FOR_IN'
                request.verified_at = matched_time
                request.attendance_log = matched_log
                request.remarks = f"Bulk match: return scan verified successfully at {matched_time}."
                request.save(update_fields=['verification_status', 'verified_at', 'attendance_log', 'remarks'])

                logger.info(f"Saving AttendanceLog as processed for Log ID {matched_log.id}")
                matched_log.processed = True
                matched_log.save(update_fields=['processed'])

                outpass_req.refresh_from_db()
                logger.info(f"Current outpass_request status after saving PV: {outpass_req.request_status}")

                results.append(_build_result(request))

    return results


def check_expired_verifications():
    """
    Scan for waiting requests that have passed their expiry time 
    and transition them to the TIME_OUT status.
    Runs periodically.
    """
    logger.info("Timeout Check Started")
    now = timezone.now()
    waiting = PendingBiometricVerification.objects.filter(
        verification_status='WAITING'
    )

    logger.info(f"check_expired_verifications executed. Current Time (UTC): {now}")
    logger.info(f"Query returned {waiting.count()} WAITING verification records.")

    count = 0
    for request in waiting:
        logger.info(f"Tracing WAITING verification: Request ID {request.request_id}, Expires At {request.expires_at}, Status {request.verification_status}")
        
        outpass_req = request.request
        outpass_req.refresh_from_db()
        
        # Exclude requests that have already exited (IN workflow) from timing out
        if outpass_req.actual_exit_datetime is not None:
            logger.info(f"Request ID {request.request_id} skipped from timeout because actual_exit_datetime is not None ({outpass_req.actual_exit_datetime})")
            continue
            
        late_grace = 0 if outpass_req.late_grace is None else outpass_req.late_grace
        if getattr(outpass_req, 'recovery_attempts', 0) > 0 and outpass_req.recovery_started_at:
            latest_allowed = request.expires_at
        else:
            latest_allowed = outpass_req.requested_exit_datetime + timedelta(minutes=late_grace)

        if now > request.expires_at or now > latest_allowed:
            if getattr(outpass_req, 'recovery_attempts', 0) >= 1:
                logger.info(f"Second Timeout Executed: Request ID {request.request_id} transitioned to TERMINATED.")
                request.verification_status = 'TIME_OUT'
                request.timed_out_at = now
                request.remarks = f"Student missed the recovered exit window. Request terminated at {now}."
                request.save(update_fields=['verification_status', 'timed_out_at', 'remarks'])
                
                outpass_req.request_status = 'TIME OUT'
                outpass_req.terminated_at = now
                outpass_req.save(update_fields=['request_status', 'terminated_at'])
            else:
                logger.info(f"Timeout Executed: Request ID {request.request_id} transitioned to TIME_OUT.")
                logger.info(f"Request ID {request.request_id} expired. now ({now}) > expires_at ({request.expires_at}) or latest_allowed ({latest_allowed})")
                request.verification_status = 'TIME_OUT'
                request.timed_out_at = now
                request.remarks = f"Automatically timed out by checker at {now} (expires at: {request.expires_at})."
                request.save(update_fields=['verification_status', 'timed_out_at', 'remarks'])
            
            count += 1
        else:
            logger.info(f"Request ID {request.request_id} NOT expired yet. now ({now}) <= expires_at ({request.expires_at}) and latest_allowed ({latest_allowed})")

    # Auto-terminate unrecovered TIME_OUT requests after 30 minutes
    unrecovered_timeouts = PendingBiometricVerification.objects.filter(
        verification_status='TIME_OUT'
    )
    for request in unrecovered_timeouts:
        outpass_req = request.request
        outpass_req.refresh_from_db()
        if outpass_req.request_status in ['TIME_OUT', 'Time out', 'TIME OUT']:
            if request.timed_out_at:
                limit = request.timed_out_at + timedelta(minutes=30)
                if now > limit:
                    logger.info(f"Auto-terminating request {outpass_req.request_id} after 30 mins in TIME_OUT.")
                    outpass_req.request_status = 'TIMEOUT_PROCESSED'
                    outpass_req.terminated_at = now
                    outpass_req.save(update_fields=['request_status', 'terminated_at'])
                    request.remarks = f"Automatically terminated after 30 minutes of timeout at {now}."
                    request.save(update_fields=['remarks'])

    return count
