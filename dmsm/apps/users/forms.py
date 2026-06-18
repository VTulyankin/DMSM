from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from dmsm.apps.core.models import Player
from dmsm.apps.monitor.handlers.player_handler import update_player_name_if_changed
import threading
import requests

class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)
        
