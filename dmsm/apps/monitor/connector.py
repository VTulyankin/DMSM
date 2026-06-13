import json
import logging
import time
import requests
import websocket
import socket
import struct
from django.conf import settings

logger = logging.getLogger(__name__)

class PterodactylConnector:
    def __init__(self):
        self.base_url = settings.PTERODACTYL_URL.rstrip('/')
        self.api_key = settings.PTERODACTYL_API_KEY
        self.server_id = settings.PTERODACTYL_SERVER_ID
        self.ws = None
        self.is_connected = False
        self.reconnect_delay = 5
        self.token = None

    def get_websocket_credentials(self):
        url = f"{self.base_url}/api/client/servers/{self.server_id}/websocket"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data['data']['token'], data['data']['socket']
        except Exception as e:
            logger.error(f"Не удалось получить учетные данные WebSocket: {e}")
            return None, None

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            event = data.get('event')
            args = data.get('args', [])

            if event == 'console output':
                for line in args:
                    logger.info(f"Консоль: {line}")
            elif event == 'status':
                for status in args:
                    if status in ('offline', 'running'):
                        logger.info(f"Статус: {status}")
            elif event == 'stats':
                if args:
                    try:
                        stats_data = json.loads(args[0])
                        state = stats_data.get('state')
                        if state in ('offline', 'running'):
                            if getattr(self, 'current_state', None) != state:
                                self.current_state = state
                                logger.info(f"Статус: {state}")
                    except json.JSONDecodeError:
                        pass
        except json.JSONDecodeError:
            logger.warning(f"Не удалось декодировать сообщение: {message}")

    def on_error(self, ws, error):
        logger.error(f"Ошибка WebSocket: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket закрыт: {close_status_code} - {close_msg}")
        self.is_connected = False
        self.reconnect()

    def on_open(self, ws):
        logger.info("Соединение WebSocket установлено. Аутентификация...")
        self.is_connected = True
        self.reconnect_delay = 5
        
        auth_message = {
            "event": "auth",
            "args": [self.token]
        }
        ws.send(json.dumps(auth_message))

    def connect(self):
        self.token, socket_url = self.get_websocket_credentials()
        
        if not self.token or not socket_url:
            logger.error("Не удалось получить учетные данные для подключения. Повторная попытка...")
            self.reconnect()
            return

        logger.info(f"Подключение к WebSocket: {socket_url}")
        
        self.ws = websocket.WebSocketApp(
            socket_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        self.ws.run_forever(ping_interval=60, ping_timeout=10, origin=self.base_url)

    def reconnect(self):
        if self.is_connected:
            return
            
        logger.info(f"Переподключение через {self.reconnect_delay} секунд...")
        time.sleep(self.reconnect_delay)
        
        self.reconnect_delay = min(self.reconnect_delay * 2, 60)
        self.connect()

    def command(self, command):
        if self.ws and self.is_connected:
            payload = {
                "event": "send command",
                "args": [command]
            }
            self.ws.send(json.dumps(payload))
        else:
            logger.error("Невозможно отправить команду, нет подключения к WebSocket")


class RCONClient:
    def __init__(self, host=None, port=None, password=None):
        self.host = host or getattr(settings, 'RCON_HOST')
        self.port = port or getattr(settings, 'RCON_PORT')
        self.password = password or getattr(settings, 'RCON_PASSWORD')
        self.sock = None
        self.reconnect_delay = 5

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, int(self.port)))
        
        packet = struct.pack('<ii', 1, 3) + self.password.encode('utf-8') + b'\x00\x00'
        self.sock.sendall(struct.pack('<i', len(packet)) + packet)
        response_length_data = self.sock.recv(4)
        
        if response_length_data:
            response_length = struct.unpack('<i', response_length_data)[0]
            self.sock.recv(response_length)

    def reconnect(self):
        if not self.sock:
            return
        
        logger.info(f"Переподключение через {self.reconnect_delay} секунд...")
        time.sleep(self.reconnect_delay)
        
        self.reconnect_delay = min(self.reconnect_delay * 2, 60)
        self.connect()

    def command(self, cmd, packet_type=2):
        if not self.sock:
            self.connect()
        try:
            req_id = 1
            packet = struct.pack('<ii', req_id, packet_type) + cmd.encode('utf-8') + b'\x00\x00'
            self.sock.sendall(struct.pack('<i', len(packet)) + packet)
            
            dummy_id = 2
            dummy_packet = struct.pack('<ii', dummy_id, 0) + b'\x00\x00'
            self.sock.sendall(struct.pack('<i', len(dummy_packet)) + dummy_packet)
            
            full_response = ""
            while True:
                response_length_data = self.sock.recv(4)
                if not response_length_data:
                    self.sock = None
                    raise ConnectionError("Empty response from server")
                    
                response_length = struct.unpack('<i', response_length_data)[0]
                response_data = b""
                
                while len(response_data) < response_length:
                    chunk = self.sock.recv(response_length - len(response_data))
                    if not chunk:
                        break
                    response_data += chunk
                    
                if len(response_data) >= 8:
                    resp_id, resp_type = struct.unpack('<ii', response_data[:8])
                    if resp_id == dummy_id:
                        break
                    if resp_id == req_id:
                        full_response += response_data[8:-2].decode('utf-8', errors='ignore')
            return full_response
        except Exception:
            self.sock = None
            raise
