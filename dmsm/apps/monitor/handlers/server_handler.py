from django.conf import settings
from django.core.cache import cache
from dmsm.apps.stats.models import Server
import logging

logger = logging.getLogger(__name__)

def sync_player_count(player_count=None, **kwargs):
    if player_count is None:
        return
    
    player_count = int(player_count)
    last = Server.objects.last()
    
    current_count = last.player_count if last else None
    
    if current_count != player_count:
        Server.objects.create(
            is_online=last.is_online if last else True,
            player_count=player_count,
            service_mode=last.service_mode if last else 'full'
        )

def update_is_online(is_online=None, handler=None, **kwargs):
    if is_online is None:
        return
        
    last = Server.objects.last()
    current_status = last.is_online if last else None
    
    if current_status != is_online:
        logger.info(f"Minecraft server state changed: {'ONLINE' if is_online else 'OFFLINE'}")
        Server.objects.create(
            is_online=is_online,
            player_count=0 if not is_online else (last.player_count if last else 0),
            service_mode=last.service_mode if last else 'full'
        )
        if not is_online:
            from dmsm.apps.monitor.handlers import session_handler
            session_handler.close_all_sessions()
            
        if handler:
            if handler.rcon:
                handler.rcon.set_server_state(is_online)
            if is_online:
                import threading
                def delayed_init():
                    handler.send_command('/scoreboard objectives add link trigger')
                    handler.send_command('/scoreboard players enable @a link')
                    handler.send_command('/version')
                threading.Timer(15.0, delayed_init).start()

def update_service_mode(new_mode=None, failed_at=None, **kwargs):
    if new_mode is None:
        return
        
    last = Server.objects.last()
    current_mode = last.service_mode if last else None
    
    if current_mode != new_mode:
        server_kwargs = {
            'is_online': last.is_online if last else False,
            'player_count': 0 if new_mode == settings.MODE_NONE else (last.player_count if last else 0),
            'service_mode': new_mode
        }
        if failed_at:
            server_kwargs['timestamp'] = failed_at
            
        Server.objects.create(**server_kwargs)

def update_server_version(version=None, **kwargs):
    if version:
        cache.set('minecraft_version', version, timeout=None)
