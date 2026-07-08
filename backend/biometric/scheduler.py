import logging
from django.conf import settings
from django.core.management import call_command
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger('biometric.sync')

scheduler = BackgroundScheduler()

def sync_logs_job():
    logger.info("Scheduler: Triggering automated biometric attendance log sync...")
    try:
        call_command('sync_logs')
        logger.info("Scheduler: Automated biometric sync completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler: Error running sync_logs job: {e}")

def check_timeouts_job():
    logger.info("Scheduler: Triggering automated biometric timeout check...")
    try:
        call_command('timeout_checker')
        logger.info("Scheduler: Automated biometric timeout check completed successfully.")
    except Exception as e:
        logger.error(f"Scheduler: Error running timeout_checker job: {e}")

def start():
    # Make interval configurable through settings (default to 30 seconds)
    interval_seconds = getattr(settings, 'BIOMETRIC_SYNC_INTERVAL_SECONDS', 10)
    
    # Enable/disable scheduler through settings
    enabled = getattr(settings, 'BIOMETRIC_SYNC_SCHEDULER_ENABLED', True)
    if not enabled:
        logger.info("Scheduler: Automated biometric sync is disabled in settings.")
        return

    # Ensure only one synchronization job runs at a time to prevent overlapping executions
    scheduler.add_job(
        sync_logs_job, 
        'interval', 
        seconds=interval_seconds, 
        id='sync_logs_job',
        replace_existing=True,
        max_instances=1
    )

    # Ensure only one timeout checker job runs at a time to prevent overlapping executions
    scheduler.add_job(
        check_timeouts_job, 
        'interval', 
        seconds=interval_seconds, 
        id='check_timeouts_job',
        replace_existing=True,
        max_instances=1
    )
    
    if not scheduler.running:
        scheduler.start()
        logger.info(f"Scheduler: Started automated biometric sync (Interval: {interval_seconds}s).")
