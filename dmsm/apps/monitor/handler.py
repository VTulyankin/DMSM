import re
from django.conf import settings
from dmsm.apps.monitor.handlers import player_handler, server_handler, session_handler

class Handler:
    def __init__(self):
        self.rcon = None
        self.ptero = None
        self.supervisor = None

        self.ROUTES = [
            (re.compile(r"(?P<nickname>\w+)\[.*?\] logged in with entity id"), [
                lambda **k: self.send_command('/list uuids')
            ]),
            (re.compile(r"(?P<nickname>\w+) lost connection: (?P<reason>.*)"), [
                lambda **k: self.send_command('/list uuids')
            ]),
            (re.compile(r"There are (?P<player_count>\d+) of a max of \d+ players online:(?P<players_str>.*)"), [
                server_handler.sync_player_count,
                player_handler.sync_players,
                session_handler.sync_sessions
            ])
        ]

    def route_event(self, event_type, **kwargs):
        if event_type == 'status':
            is_online = kwargs.get('is_online')
            server_handler.update_is_online(is_online=is_online)
            if self.rcon:
                self.rcon.set_server_state(is_online)

    def route_text(self, text):
        for pattern, methods in self.ROUTES:
            match = pattern.search(text)
            if match:
                data = match.groupdict()
                
                if 'players_str' in data:
                    raw_str = data.pop('players_str').strip()
                    players_dict = {}
                    if raw_str:
                        for p in raw_str.split(','):
                            if '(' in p:
                                name, uuid = p.strip().split(' (')
                                players_dict[name] = uuid.rstrip(')')
                    data['players_dict'] = players_dict
                
                for method in methods:
                    try:
                        method(**data)
                    except Exception:
                        pass

    def send_command(self, cmd):
        if not self.supervisor:
            return

        mode = self.supervisor.current_mode
        response = None

        if mode in [None, settings.MODE_FULL, settings.MODE_RCON_ONLY]:
            if self.rcon:
                response = self.rcon.command(cmd)
                if response:
                    self.route_text(response)
                    return

        if mode in [None, settings.MODE_FULL, settings.MODE_PTERODACTYL_ONLY]:
            if not response and self.ptero:
                self.ptero.command(cmd)
