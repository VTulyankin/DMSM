import socket
import struct
from django.conf import settings

class MinecraftRCONClient:
    def __init__(self, host=None, port=None, password=None):
        self.host = host or getattr(settings, 'RCON_HOST')
        self.port = port or getattr(settings, 'RCON_PORT')
        self.password = password or getattr(settings, 'RCON_PASSWORD')
        self.sock = None

    def connect(self):
        self.disconnect()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, int(self.port)))
        
        packet = struct.pack('<ii', 1, 3) + self.password.encode('utf-8') + b'\x00\x00'
        self.sock.sendall(struct.pack('<i', len(packet)) + packet)
        response_length_data = self.sock.recv(4)
        
        if response_length_data:
            response_length = struct.unpack('<i', response_length_data)[0]
            self.sock.recv(response_length)

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def command(self, cmd, packet_type=2):
        if not self.sock:
            self.connect()
        try:
            packet = struct.pack('<ii', 1, packet_type) + cmd.encode('utf-8') + b'\x00\x00'
            self.sock.sendall(struct.pack('<i', len(packet)) + packet)
            response_length_data = self.sock.recv(4)
            
            if not response_length_data:
                self.disconnect()
                raise ConnectionError("Empty response from server")
                
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
            self.disconnect()
            raise
