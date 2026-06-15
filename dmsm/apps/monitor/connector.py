import json
import time
import requests
import websocket
import socket
import struct
import threading
from django.conf import settings

class Connector:
    def handle_error(self, service_name):
        errors = self.supervisor.report_connection(service_name, False)
        if errors >= self.supervisor.HARD_LIMIT:
            return False
            
        delay = self.supervisor.RECONNECT_DELAY
        if errors >= self.supervisor.SOFT_LIMIT:
            delay *= 2 ** (errors - self.supervisor.SOFT_LIMIT + 1)
            
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
                    self.handler.handle_ptero_log(line)
            elif event == 'stats' and args:
                state = json.loads(args[0]).get('state')
                if state and state != self.current_state:
                    self.current_state = state
                    self.handler.handle_status(state)
        except Exception:
            pass

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, close_status_code, close_msg):
        pass

    def on_open(self, ws):
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
            self.ws.send(json.dumps({"event": "send command", "args": [command]}))


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

    def connect(self):
        if not self.host or not self.port:
            return
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.host, int(self.port)))
            
            packet = struct.pack('<ii', 1, 3) + self.password.encode('utf-8') + b'\x00\x00'
            self.sock.sendall(struct.pack('<i', len(packet)) + packet)
            response_length_data = self.sock.recv(4)
            if response_length_data:
                self.sock.recv(struct.unpack('<i', response_length_data)[0])
                
            self.supervisor.report_connection('rcon', True)
        except Exception:
            self.sock = None

    def reconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None
        self.connect()

    def command(self, cmd, packet_type=2, retries=1):
        with self.lock:
            if not self.sock:
                self.connect()
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
                if retries > 0:
                    return self.command(cmd, packet_type, retries - 1)
                return ""

    def polling(self):
        last_uuids = None
        while True:
            uuids = self.command('/list uuids')
            if not uuids:
                if not self.handle_error('rcon'):
                    break
                continue
            else:
                self.supervisor.report_connection('rcon', True)
                if uuids != last_uuids:
                    last_uuids = uuids
                    self.handler.handle_rcon_uuids(uuids)
            
            time.sleep(self.interval)


