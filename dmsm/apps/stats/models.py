from django.db import models

class Player(models.Model):
    uuid = models.CharField(max_length=36, unique=True)
    nickname = models.CharField(max_length=16)
    first_seen = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nickname

class Session(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    login_time = models.DateTimeField()
    logout_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.player.nickname} ({self.login_time} - {self.logout_time or 'present'})"

class Server(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    is_online = models.BooleanField()
    player_count = models.IntegerField()

    def __str__(self):
        return f"Server status at {self.timestamp}: {'Online' if self.is_online else 'Offline'}, {self.player_count} players"
