from django.db import models
from django.contrib.auth.models import User
from dmsm.apps.core.models import Player

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    is_pending_whitelist = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"
