import os
import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Only start the scheduler in the actual web-server process:
        #   - Dev (runserver): child process has RUN_MAIN='true'
        #   - Production (gunicorn): 'runserver' won't be in argv
        # Skip for all other management commands (poll, migrate, etc.)
        argv = getattr(sys, 'argv', [])
        is_runserver = 'runserver' in argv
        is_runserver_child = os.environ.get('RUN_MAIN') == 'true'

        if is_runserver and not is_runserver_child:
            # Parent reloader process — let the child handle it
            return
        if not is_runserver and any(
            cmd in argv for cmd in ['poll', 'send_digest', 'migrate',
                                    'makemigrations', 'collectstatic', 'shell',
                                    'createsuperuser', 'test']
        ):
            return

        try:
            from .scheduler import start_scheduler
            start_scheduler()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Scheduler failed to start: %s", exc)
