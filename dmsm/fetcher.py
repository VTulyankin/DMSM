import re
import time
from django.utils import timezone
from django.conf import settings
from dmsm.rcon_client import MinecraftRCONClient
from dmsm.monitoring.models import Server, Player, Session

class ServerFetcher:
    def __init__(self):
        self.interval = getattr(settings, 'FETCH_INTERVAL', 60)
        self.client = MinecraftRCONClient()
        
        last_server_status = Server.objects.order_by('-timestamp').first()
        self.last_is_online = last_server_status.is_online if last_server_status else None
        self.last_player_count = last_server_status.player_count if last_server_status else None

    def parse_response(self, response):
        count_match = re.search(r'(\d+)\s+of\s+a\s+max', response)
        player_count = int(count_match.group(1)) if count_match else 0
        players = [{"nickname": n, "uuid": u} for n, u in re.findall(r'([a-zA-Z0-9_]+)\s*\(([a-fA-F0-9-]+)\)', response)]
        return player_count, players

    def fetch(self):
        response = self.client.command("list uuids")
        return self.parse_response(response)

    def process_data(self, player_count, players):
        now = timezone.now()

        if self.last_is_online is not True or self.last_player_count != player_count:
            Server.objects.create(
                is_online=True,
                player_count=player_count
            )
            self.last_is_online = True
            self.last_player_count = player_count

        active_uuids = set()
        
        for p_data in players:
            active_uuids.add(p_data["uuid"])
            player, created = Player.objects.get_or_create(
                uuid=p_data["uuid"],
                defaults={'nickname': p_data["nickname"]}
            )
            
            if not created and player.nickname != p_data["nickname"]:
                player.nickname = p_data["nickname"]
                player.save(update_fields=['nickname'])

            session = Session.objects.filter(player=player, logout_time__isnull=True).first()
            if session:
                session.last_seen = now
                session.save(update_fields=['last_seen'])
            else:
                Session.objects.create(
                    player=player,
                    login_time=now,
                    last_seen=now
                )

        Session.objects.filter(logout_time__isnull=True).exclude(player__uuid__in=active_uuids).update(logout_time=now)

    def handle_offline(self):
        now = timezone.now()
        
        if self.last_is_online is not False:
            Server.objects.create(
                is_online=False,
                player_count=0
            )
            self.last_is_online = False
            self.last_player_count = 0
            
        Session.objects.filter(logout_time__isnull=True).update(logout_time=now)

    def start_loop(self):
        while True:
            try:
                count, players = self.fetch()
                self.process_data(count, players)
            except Exception:
                self.handle_offline()

            time.sleep(self.interval)

if __name__ == '__main__':
    ServerFetcher().start_loop()