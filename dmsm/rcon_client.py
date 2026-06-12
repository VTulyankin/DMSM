import socket
import struct
import time
from django.conf import settings

class MinecraftRCONClient:
    def __init__(self, host=None, port=None, password=None):
        self.host = host or getattr(settings, 'RCON_HOST')
        self.port = port or getattr(settings, 'RCON_PORT')
        self.password = password or getattr(settings, 'RCON_PASSWORD')
        self.interval = getattr(settings, 'FETCH_INTERVAL', 60)
        self.sock = None

    def connect(self):
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5.0)
                self.sock.connect((self.host, int(self.port)))
                
                packet = struct.pack('<ii', 1, 3) + self.password.encode('utf-8') + b'\x00\x00'
                self.sock.sendall(struct.pack('<i', len(packet)) + packet)
                response_length_data = self.sock.recv(4)
                
                if response_length_data:
                    response_length = struct.unpack('<i', response_length_data)[0]
                    self.sock.recv(response_length)
                
                break
            except Exception:
                print("offline")
                self.disconnect()
                time.sleep(self.interval)

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def command(self, cmd, packet_type=2):
        while True:
            if not self.sock:
                self.connect()
            try:
                packet = struct.pack('<ii', 1, packet_type) + cmd.encode('utf-8') + b'\x00\x00'
                self.sock.sendall(struct.pack('<i', len(packet)) + packet)
                response_length_data = self.sock.recv(4)
                
                if not response_length_data:
                    self.connect()
                    continue
                    
                response_length = struct.unpack('<i', response_length_data)[0]
                response_data = b""
                
                while len(response_data) < response_length:
                    chunk = self.sock.recv(response_length - len(response_data))
                    if not chunk:
                        break
                    response_data += chunk
                    
                if len(response_data) >= 8:
                    return response_data[8:-2].decode('utf-8', errors='ignore')
                return ""
            except Exception:
                self.connect()