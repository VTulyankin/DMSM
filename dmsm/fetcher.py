import os
import sys

if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmsm.settings')
    import django
    django.setup()

import re
import time
from django.conf import settings
from dmsm.rcon_client import MinecraftRCONClient

class ServerFetcher:
    def __init__(self):
        self.interval = getattr(settings, 'FETCH_INTERVAL', 60)
        self.client = MinecraftRCONClient()

    def parse_response(self, response):
        count_match = re.search(r'(\d+)\s+of\s+a\s+max', response)
        player_count = int(count_match.group(1)) if count_match else 0
        players = [{"nickname": n, "uuid": u} for n, u in re.findall(r'([a-zA-Z0-9_]+)\s*\(([a-fA-F0-9-]+)\)', response)]
        return player_count, players

    def fetch(self):
        response = self.client.command("list uuids")
        return self.parse_response(response)

    def start_loop(self):
        self.client.connect()
        while True:
            count, players = self.fetch()
            print(count, players)
            time.sleep(self.interval)

if __name__ == '__main__':
    ServerFetcher().start_loop()