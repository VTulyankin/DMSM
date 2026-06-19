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
            level=logging.INFO,
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
            threading.Thread(target=rcon_connector.scoreboard_thread, daemon=True).start()

        time.sleep(5)
        handler.send_command('/list uuids')
        handler.send_command('/scoreboard objectives add link trigger')
        handler.send_command('/scoreboard players enable @a link')
        handler.send_command('/version')

        from django.conf import settings
        from dmsm.apps.users.models import UserProfile
        
        def process_whitelist_queue():
            while True:
                time.sleep(10)
                try:
                    if supervisor.mode != 'offline':
                        pending_profiles = UserProfile.objects.filter(is_pending_whitelist=True)
                        for profile in pending_profiles:
                            handler.send_command(f'whitelist add {profile.user.username}')
                            profile.is_pending_whitelist = False
                            profile.save()
                except Exception as e:
                    logging.error(f"Error processing whitelist queue: {e}")

        if getattr(settings, 'WHITELIST_MODE', False):
            threading.Thread(target=process_whitelist_queue, daemon=True).start()

        def heartbeat_loop():
            from dmsm.apps.core.models import Monitor
            from django.utils import timezone
            
            current_monitor = None
            current_mode = None
            
            while True:
                try:
                    mode = supervisor.current_mode or 'full'
                    if not current_monitor or mode != current_mode:
                        current_monitor = Monitor.objects.create(monitor_mode=mode)
                        current_mode = mode
                    else:
                        Monitor.objects.filter(id=current_monitor.id).update(live_time=timezone.now())
                except Exception as e:
                    logging.error(f"Error updating monitor heartbeat: {e}")
                time.sleep(20)

        threading.Thread(target=heartbeat_loop, daemon=True).start()

        while True:
            time.sleep(1)
