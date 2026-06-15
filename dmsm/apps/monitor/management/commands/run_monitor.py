import time
import threading
from django.core.management.base import BaseCommand
from dmsm.apps.monitor.connector import PterodactylConnector, RCONConnector
from dmsm.apps.monitor.handler import Handler
from dmsm.apps.monitor.supervisor import Supervisor

import logging

class Command(BaseCommand):

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.CRITICAL,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            force=True
        )
        handler = Handler()
        supervisor = Supervisor()
        handler.supervisor = supervisor
        
        has_ptero = supervisor.services['ptero']['has_config']
        has_rcon = supervisor.services['rcon']['has_config']
        
        if not has_ptero and not has_rcon:
            return

        if has_ptero:
            ptero_connector = PterodactylConnector(handler=handler, supervisor=supervisor)
            handler.ptero = ptero_connector
            threading.Thread(target=ptero_connector.connect, daemon=True).start()
            
        if has_rcon:
            rcon_connector = RCONConnector(handler=handler, supervisor=supervisor)
            handler.rcon = rcon_connector
            threading.Thread(target=rcon_connector.maintain_connection, daemon=True).start()
            threading.Thread(target=rcon_connector.uuids_thread, daemon=True).start()

        time.sleep(5)
        handler.send_command('/list uuids')

        while True:
            time.sleep(1)
