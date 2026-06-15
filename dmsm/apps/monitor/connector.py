import json
import time
import requests
import websocket
import socket
import struct
import threading
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class Connector:
    def handle_error(self, service_name):
        errors = self.supervisor.report_connection(service_name, False)
        if errors >= self.supervisor.HARD_LIMIT:
            logger.error(f"{service_name} reached HARD LIMIT of errors.")
            return False
            
        delay = self.supervisor.RECONNECT_DELAY
        if errors >= self.supervisor.SOFT_LIMIT:
            delay *= 2 ** (errors - self.supervisor.SOFT_LIMIT + 1)
            
        logger.debug(f"{service_name} reconnecting in {delay}s...")
        time.sleep(delay)
        return True


class PterodactylConnector(Connector):
    def __init__(self, handler, supervisor):
        self.handler = handler
        self.supervisor = supervisor
        self.base_url = settings.PTERODACTYL_URL.rstrip('/') if settings.PTERODACTYL_URL else ''
        self.api_key = settings.PTERODACTYL_API_KEY
        self.server_id = settings.PTERODACTYL_SERVER_ID
        self.ws = None
        self.token = None
        self.current_state = None

    def get_websocket_credentials(self):
        if not self.base_url:
            return None, None
        url = f"{self.base_url}/api/client/servers/{self.server_id}/websocket"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=5)
            data = response.json().get('data', {})
            return data.get('token'), data.get('socket')
        except Exception:
            return None, None

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            event = data.get('event')
            args = data.get('args', [])

            if event == 'console output':
                for line in args:
                    self.handler.route_text(line)
            elif event == 'stats' and args:
                state = json.loads(args[0]).get('state')
                if state and state != self.current_state:
                    self.current_state = state
                    self.handler.route_event('status', is_online=(state == 'running'))
        except Exception:
            pass

    def on_error(self, ws, error):
        logger.error(f"Pterodactyl websocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"Pterodactyl websocket closed: {close_status_code} {close_msg}")

    def on_open(self, ws):
        logger.info("Pterodactyl websocket opened. Authenticating...")
        self.supervisor.report_connection('ptero', True)
        ws.send(json.dumps({"event": "auth", "args": [self.token]}))

    def connect(self):
        while True:
            self.token, socket_url = self.get_websocket_credentials()
            if not self.token or not socket_url:
                if not self.handle_error('ptero'):
                    break
                continue

            self.ws = websocket.WebSocketApp(
                socket_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            self.ws.run_forever(ping_interval=60, ping_timeout=10, origin=self.base_url)
            
            if not self.handle_error('ptero'):
                break

    def command(self, command):
        if self.ws:
            try:
                self.ws.send(json.dumps({"event": "send command", "args": [command]}))
            except Exception as e:
                logger.warning(f"Failed to send command via Pterodactyl: {e}")


class RCONConnector(Connector):
    def __init__(self, handler, supervisor):
        self.handler = handler
        self.supervisor = supervisor
        self.host = settings.RCON_HOST
        self.port = settings.RCON_PORT
        self.password = settings.RCON_PASSWORD
        self.sock = None
        self.interval = int(settings.RCON_INTERVAL) if settings.RCON_INTERVAL else 5
        self.lock = threading.Lock()
        self.req_id = 0
        self.server_is_online = True
        self.auth_failed = False

    def connect(self):
        if not self.host or not self.port:
            self.supervisor.report_connection('rcon', False)
            return
        try:
            logger.debug(f"Connecting to RCON at {self.host}:{self.port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, int(self.port)))
            
            packet = struct.pack('<ii', 1, 3) + self.password.encode('utf-8') + b'\x00\x00'
            self.sock.sendall(struct.pack('<i', len(packet)) + packet)
            
            response_length_data = self.sock.recv(4)
            if not response_length_data:
                raise ConnectionError("Connection closed by remote host during authentication.")
                
            response_length = struct.unpack('<i', response_length_data)[0]
            response_data = self.sock.recv(response_length)
            if len(response_data) >= 8:
                resp_id, resp_type = struct.unpack('<ii', response_data[:8])
                if resp_id == -1:
                    raise PermissionError("RCON authentication failed: invalid password.")
            else:
                raise ConnectionError("Invalid RCON response length.")
                
            logger.info("RCON connection and authentication successful.")
            self.supervisor.report_connection('rcon', True)
        except PermissionError as e:
            logger.error(f"RCON Authentication failed: {e}")
            errors = self.supervisor.report_connection('rcon', False)
            if errors >= self.supervisor.HARD_LIMIT:
                logger.critical("RCON HARD LIMIT reached for auth errors. Disabling RCON.")
                self.auth_failed = True
            self.sock = None
        except ConnectionRefusedError as e:
            logger.warning(f"RCON Connection refused (server likely offline): {e}")
            errors = self.supervisor.report_connection('rcon', False)
            if errors >= self.supervisor.SOFT_LIMIT:
                logger.warning("RCON SOFT LIMIT reached. Marking server as offline.")
                from dmsm.apps.monitor.handlers import server_handler
                server_handler.update_is_online(is_online=False)
            self.sock = None
        except Exception as e:
            logger.warning(f"RCON Connection error: {e}")
            self.sock = None
            self.supervisor.report_connection('rcon', False)

    def reconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.connect()

    def command(self, cmd, packet_type=2):
        with self.lock:
            if not self.sock:
                return ""
            try:
                self.req_id += 1
                current_id = self.req_id
                
                packet = struct.pack('<ii', current_id, packet_type) + cmd.encode('utf-8') + b'\x00\x00'
                self.sock.sendall(struct.pack('<i', len(packet)) + packet)
                
                self.req_id += 1
                dummy_id = self.req_id
                dummy_packet = struct.pack('<ii', dummy_id, packet_type) + b'\x00\x00'
                self.sock.sendall(struct.pack('<i', len(dummy_packet)) + dummy_packet)
                
                full_response = ""
                
                while True:
                    response_length_data = self.sock.recv(4)
                    if not response_length_data:
                        self.sock = None
                        raise ConnectionError()
                        
                    response_length = struct.unpack('<i', response_length_data)[0]
                    response_data = b""
                    
                    while len(response_data) < response_length:
                        chunk = self.sock.recv(response_length - len(response_data))
                        if not chunk:
                            break
                        response_data += chunk
                        
                    if len(response_data) >= 8:
                        resp_id, _ = struct.unpack('<ii', response_data[:8])
                        payload = response_data[8:-2].decode('utf-8', errors='ignore')
                        
                        if resp_id == current_id:
                            full_response += payload
                        elif resp_id == dummy_id:
                            return full_response
            except Exception:
                self.sock = None
                self.supervisor.report_connection('rcon', False)
                return ""
    
    def maintain_connection(self):
        while True:
            try:
                if self.auth_failed:
                    break
                    
                if not self.server_is_online:
                    time.sleep(1)
                    continue
                    
                if not self.sock:
                    with self.lock:
                        if not self.sock:
                            self.connect()
                
                time.sleep(1)
            except Exception as e:
                logger.error(f"Unexpected error in maintain_connection: {e}")
                time.sleep(1)

    def uuids_thread(self):
        while True:
            try:
                if self.auth_failed:
                    break
                
                if self.sock:
                    mode = self.supervisor.current_mode
                    if mode in [None, settings.MODE_FULL, settings.MODE_RCON_ONLY]:
                        self.handler.send_command('/list uuids')
                    
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Unexpected error in uuids_thread: {e}")
                time.sleep(self.interval)

    def set_server_state(self, is_online):
        self.server_is_online = is_online
