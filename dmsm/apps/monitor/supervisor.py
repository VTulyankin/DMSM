from django.core.cache import cache
from django.utils import timezone
from dmsm import settings
from dmsm.apps.stats.models import Server
import logging

logger = logging.getLogger(__name__)

class Supervisor:
    SOFT_LIMIT = 3
    HARD_LIMIT = 10
    RECONNECT_DELAY = 5

    def __init__(self):
        has_ptero = bool(settings.PTERODACTYL_URL and settings.PTERODACTYL_API_KEY and settings.PTERODACTYL_SERVER_ID)
        has_rcon = bool(settings.RCON_HOST and settings.RCON_PORT and settings.RCON_PASSWORD)
        
        self.services = {
            'ptero': {
                'has_config': has_ptero,
                'errors': None if has_ptero else self.HARD_LIMIT,
                'failed_at': None
            },
            'rcon': {
                'has_config': has_rcon,
                'errors': None if has_rcon else self.HARD_LIMIT,
                'failed_at': None
            }
        }
        
        self.current_mode = None

    def report_connection(self, service_name, is_connected):
        if service := self.services.get(service_name):
            if is_connected:
                if service['errors'] != 0:
                    logger.info(f"Service {service_name} connection established/restored.")
                service['errors'] = 0
                service['failed_at'] = None
            else:
                if service['errors'] == 0:
                    logger.warning(f"Service {service_name} connection lost.")
                    service['failed_at'] = timezone.now()
                service['errors'] = (service['errors'] or 0) + 1
            self.update_mode()
            return service['errors']
        return self.HARD_LIMIT

    def update_mode(self):
        for data in self.services.values():
            if data['errors'] is None:
                return
                
        ptero_ok = self.services['ptero']['errors'] < self.SOFT_LIMIT
        rcon_ok = self.services['rcon']['errors'] < self.SOFT_LIMIT
        
        new_mode = {
            (True, True): settings.MODE_FULL,
            (True, False): settings.MODE_PTERODACTYL_ONLY,
            (False, True): settings.MODE_RCON_ONLY,
            (False, False): settings.MODE_NONE
        }[(ptero_ok, rcon_ok)]
        
        if new_mode != self.current_mode:
            logger.info(f"Service mode changed from {self.current_mode} to {new_mode}")
            self.current_mode = new_mode
            cache.set('service_mode', self.current_mode, timeout=None)
            
            failed_times = [s.get('failed_at') for s in self.services.values() if s.get('failed_at')]
            failed_at = max(failed_times) if failed_times else None
            
            from dmsm.apps.monitor.handlers import server_handler
            server_handler.update_service_mode(new_mode=new_mode, failed_at=failed_at)
            
            if new_mode == settings.MODE_NONE:
                from dmsm.apps.monitor.handlers import session_handler
                session_handler.close_all_sessions(failed_at=failed_at)
