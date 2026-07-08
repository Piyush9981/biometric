from django.apps import AppConfig


class BiometricConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'biometric'

    def ready(self):
        try:
            import biometric.signals
        except ImportError:
            pass

        # Start background biometric sync scheduler automatically
        import os
        import sys
        
        # Only start if we are running runserver or a production server (WSGI/ASGI)
        # Avoid running during tests, makemigrations, migrate, etc.
        is_manage_command = 'manage.py' in sys.argv
        is_runserver = 'runserver' in sys.argv
        
        if not is_manage_command or is_runserver:
            # If we are using Django runserver with reloader, only run in the child process (RUN_MAIN=true)
            if is_runserver and os.environ.get('RUN_MAIN') != 'true':
                return
            
            try:
                from biometric import scheduler
                scheduler.start()
            except Exception as e:
                import logging
                logger = logging.getLogger('biometric.sync')
                logger.error(f"Scheduler: Failed to start background scheduler: {e}")
