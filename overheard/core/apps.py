import os
import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        argv = getattr(sys, 'argv', [])
        is_runserver = 'runserver' in argv
        is_runserver_child = os.environ.get('RUN_MAIN') == 'true'

        if is_runserver and not is_runserver_child:
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
