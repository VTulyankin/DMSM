from django.utils import timezone
from dmsm.apps.stats.models import Player, Session

def sync_sessions(players_dict=None, **kwargs):
    if players_dict is None:
        return
    
    now = timezone.now()
    online_uuids = list(players_dict.values())
    
    for nickname, uuid in players_dict.items():
        try:
            player = Player.objects.get(uuid=uuid)
            active_session = Session.objects.filter(player=player, logout_time__isnull=True).first()
            if not active_session:
                Session.objects.create(player=player, login_time=now)
        except Player.DoesNotExist:
            pass
            
    active_sessions = Session.objects.filter(logout_time__isnull=True)
    for session in active_sessions:
        if session.player.uuid not in online_uuids:
            session.logout_time = now
            session.save()

def close_all_sessions(failed_at=None):
    now = failed_at or timezone.now()
    active_sessions = Session.objects.filter(logout_time__isnull=True)
    active_sessions.update(logout_time=now)
