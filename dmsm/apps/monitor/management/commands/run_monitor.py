import time
import threading
from django.core.management.base import BaseCommand
from dmsm.apps.monitor.connector import PterodactylConnector, RCONConnector
from dmsm.apps.monitor.handler import Handler
from dmsm.apps.monitor.supervisor import Supervisor

def run_rcon_monitoring(handler, supervisor):
    connector = RCONConnector(handler=handler, supervisor=supervisor)
    connector.polling()

def run_pterodactyl_monitoring(handler, supervisor):
    connector = PterodactylConnector(handler=handler, supervisor=supervisor)
    connector.connect()

class Command(BaseCommand):
    def handle(self, *args, **options):
        handler = Handler()
        supervisor = Supervisor()
        
        has_ptero = supervisor.services['ptero']['has_config']
        has_rcon = supervisor.services['rcon']['has_config']
        
        if not has_ptero and not has_rcon:
            return

        if has_ptero:
            ptero_thread = threading.Thread(target=run_pterodactyl_monitoring, args=(handler, supervisor), daemon=True)
            ptero_thread.start()
            
        if has_rcon:
            rcon_thread = threading.Thread(target=run_rcon_monitoring, args=(handler, supervisor), daemon=True)
            rcon_thread.start()

        while True:
            time.sleep(1)
