from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from dmsm.apps.core.models import Session, Server, Player
import datetime

def api_online_events(request):
    from django.utils import timezone
    from dmsm.apps.core.models import Server, Monitor
    import datetime
    
    servers = Server.objects.all().order_by('timestamp')
    events = []
    
    for server in servers:
        if not server.is_online:
            events.append({
                'time': server.timestamp.isoformat(),
                'type': 'downtime'
            })
        else:
            events.append({
                'time': server.timestamp.isoformat(),
                'type': 'uptime',
                'player_count': server.player_count
            })
            
    events.sort(key=lambda x: x['time'])
    
    monitor_events = []
    monitors = Monitor.objects.all().order_by('timestamp')
    for m in monitors:
        monitor_events.append({
            'start': m.timestamp.isoformat(),
            'end': m.live_time.isoformat(),
            'mode': m.monitor_mode
        })
        
    return JsonResponse({'events': events, 'monitors': monitor_events})

def api_players_at_time(request):
    timestamp_str = request.GET.get('timestamp')
    if not timestamp_str:
        return JsonResponse({'error': 'Missing timestamp'}, status=400)
        
    if timestamp_str == 'now':
        timestamp = datetime.datetime.now(datetime.timezone.utc)
    else:
        try:
            timestamp_ms = int(timestamp_str)
            timestamp = datetime.datetime.fromtimestamp(timestamp_ms / 1000.0, tz=datetime.timezone.utc)
        except ValueError:
            try:
                timestamp = parse_datetime(timestamp_str)
                if not timestamp:
                    raise ValueError
            except ValueError:
                return JsonResponse({'error': 'Invalid timestamp format'}, status=400)

    active_sessions = Session.objects.filter(
        login_time__lte=timestamp
    ).exclude(
        logout_time__lt=timestamp
    ).select_related('player')
    
    # Use dictionary to ensure uniqueness by username while keeping uuid
    players_dict = {}
    for session in active_sessions:
        players_dict[session.player.nickname] = session.player.uuid
        
    players_list = [{'username': nick, 'uuid': uuid} for nick, uuid in players_dict.items()]
    
    return JsonResponse({'players': players_list})

def api_player_sessions(request, nickname):
    player = Player.objects.filter(nickname=nickname).first()
    if not player:
        return JsonResponse({'error': 'Player not found'}, status=404)
        
    sessions = Session.objects.filter(player=player).order_by('login_time')
    
    raw_sessions = []
    is_online = False
    
    for session in sessions:
        login_iso = session.login_time.isoformat() if session.login_time else None
        logout_iso = session.logout_time.isoformat() if session.logout_time else None
        
        if not session.logout_time:
            is_online = True
            
        if login_iso:
            raw_sessions.append({
                'login': login_iso,
                'logout': logout_iso
            })
            
    return JsonResponse({
        'nickname': player.nickname,
        'uuid': player.uuid,
        'first_seen': player.first_seen.isoformat() if player.first_seen else None,
        'status': 'online' if is_online else 'offline',
        'sessions': raw_sessions
    })
