import os
import sys
import django
import logging
import threading

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.append(project_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmsm.settings')
django.setup()

from dmsm.apps.monitor.connector import PterodactylConnector, RCONClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def command_loop(rcon):
    while True:
        try:
            cmd = input()
            if cmd.strip():
                if cmd.strip().lower() in ('exit', 'quit'):
                    os._exit(0)
                try:
                    result = rcon.command(cmd.strip())
                    if result:
                        print(f"Ответ RCON:\n{result}")
                except Exception as e:
                    print(f"Ошибка RCON: {e}")
        except (KeyboardInterrupt, EOFError):
            os._exit(0)

if __name__ == "__main__":    
    pterodactyl = PterodactylConnector()
    ws_thread = threading.Thread(target=pterodactyl.connect, daemon=True)
    ws_thread.start()
    
    rcon = RCONClient()
    try:
        rcon.connect()
        print("Успешное подключение к RCON.")
    except Exception as e:
        print(f"Ошибка подключения к RCON: {e}")
    
    command_loop(rcon)
