import os
import threading
from django.apps import AppConfig

class MonitoringConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dmsm.monitoring'

    def ready(self):
        if os.environ.get('RUN_MAIN'):
            from dmsm.fetcher import ServerFetcher
            
            fetcher = ServerFetcher()
            thread = threading.Thread(target=fetcher.start_loop, daemon=True)
            thread.start()
