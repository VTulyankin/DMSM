import logging
import requests
import json
import copy
import threading
from django.core.signing import dumps
from django.conf import settings
from django.core.cache import cache
from dmsm.apps.core.models import Player

logger = logging.getLogger(__name__)

def update_player_name_if_changed(existing_player):
    clean_uuid = existing_player.uuid.replace('-', '')
    resp = requests.get(f'https://sessionserver.mojang.com/session/minecraft/profile/{clean_uuid}', timeout=5)
    
    if resp.status_code == 200:
        data = resp.json()
        new_name = data.get('name')
        if new_name and new_name != existing_player.nickname:
            existing_player.nickname = new_name
            existing_player.save()
            if hasattr(existing_player, 'userprofile'):
                user = existing_player.userprofile.user
                user.username = new_name
                user.save()
            return True
        return False
    elif resp.status_code in [204, 404, 400]:
        return False
    
    resp.raise_for_status()
    return False

def sync_players(players_dict=None, handler=None, **kwargs):
    if players_dict is None:
        return
    
    for nickname, uuid in players_dict.items():
        existing = Player.objects.filter(nickname=nickname).exclude(uuid=uuid).first()
        if existing:
            def resolve_conflict(nick, new_uuid, existing_player, hndl):
                try:
                    changed = update_player_name_if_changed(existing_player)
                    if not changed:
                        existing_player.uuid = new_uuid
                        existing_player.save()
                except Exception as e:
                    logger.warning(f"Mojang API failed for {existing_player.uuid}: {e}")
                    if hndl:
                        threading.Timer(15.0, hndl.send_command, args=['/list uuids']).start()
                    return
                
                if hndl:
                    hndl.send_command('/list uuids')

            threading.Thread(target=resolve_conflict, args=(nickname, uuid, existing, handler), daemon=True).start()
            continue
        
        player, created = Player.objects.get_or_create(
            uuid=uuid, 
            defaults={'nickname': nickname}
        )
        
        if not created and player.nickname != nickname:
            player.nickname = nickname
            player.save()
            if hasattr(player, 'userprofile'):
                user = player.userprofile.user
                user.username = nickname
                user.save()

def handle_trigger_link(nickname, score=None, handler=None, **kwargs):
    player = Player.objects.filter(nickname=nickname).first()
    
    if not player:
        if handler:
            handler.send_command('/list uuids')
        return

    from dmsm.apps.core.models import Session
    active_session = Session.objects.filter(player=player, logout_time__isnull=True).exists()
    if not active_session:
        if handler:
            msg = json.dumps(["", {"text": "Ваш профиль синхронизируется. Пожалуйста, подождите пару минут и попробуйте снова.", "color": "red"}], ensure_ascii=False)
            handler.send_command(f'/tellraw {nickname} {msg}')
            handler.send_command(f'/scoreboard players reset {nickname} link')
            handler.send_command(f'/scoreboard players enable {nickname} link')
        return

    token = dumps({'nickname': nickname})
    site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
    link = f"{site_url}/users/link/{token}/"
    
    version = cache.get('minecraft_version', '1.20')
    is_new = False
    try:
        parts = [int(p) for p in version.split('.')]
        if len(parts) >= 2:
            if parts[0] > 1:
                is_new = True
            elif parts[0] == 1:
                if parts[1] > 21 or (parts[1] == 21 and len(parts) >= 3 and parts[2] >= 5):
                    is_new = True
    except Exception:
        pass

    click_attr = "click_event" if is_new else "clickEvent"
    action_val_key = "url" if is_new else "value"
    
    template = settings.TELLRAW_LINK_MESSAGE
    
    message_json = [""]
    
    for comp in template:
        comp_copy = copy.deepcopy(comp)
        
        is_link = comp_copy.pop('is_link', False)
        if is_link:
            comp_copy[click_attr] = {
                "action": "open_url",
                action_val_key: link
            }
        
        message_json.append(comp_copy)
    
    cmd = f'/tellraw {nickname} {json.dumps(message_json, ensure_ascii=False)}'
    
    if handler:
        handler.send_command(cmd)
        handler.send_command(f'/scoreboard players reset {nickname} link')
        handler.send_command(f'/scoreboard players enable {nickname} link')
