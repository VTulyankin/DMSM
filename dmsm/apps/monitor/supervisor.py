from django.core.cache import cache
from dmsm import settings
from dmsm.apps.stats.models import Server

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
                'errors': None if has_ptero else self.SOFT_LIMIT
            },
            'rcon': {
                'has_config': has_rcon,
                'errors': None if has_rcon else self.SOFT_LIMIT
            }
        }
        
        self.current_mode = None

    def report_connection(self, service_name, is_connected):
        if service := self.services.get(service_name):
            service['errors'] = 0 if is_connected else (service['errors'] or 0) + 1
            self.update_mode()
            return service['errors']
        return self.HARD_LIMIT

    def update_mode(self):
        for data in self.services.values():
            if data['errors'] is None or (0 < data['errors'] < self.SOFT_LIMIT):
                return
                
        new_mode = {
            (True, True): settings.MODE_FULL,
            (True, False): settings.MODE_PTERODACTYL_ONLY,
            (False, True): settings.MODE_RCON_ONLY,
            (False, False): settings.MODE_NONE
        }[(self.services['ptero']['errors'] == 0, self.services['rcon']['errors'] == 0)]
        
        if new_mode != self.current_mode:
            self.current_mode = new_mode
            cache.set('service_mode', self.current_mode, timeout=None)
            
            last = Server.objects.last()
            Server.objects.create(
                is_online=last.is_online if last else False,
                player_count=last.player_count if last else 0,
                service_mode=new_mode
            )
