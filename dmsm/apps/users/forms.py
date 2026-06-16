from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from dmsm.apps.stats.models import Player
from dmsm.apps.monitor.handlers.player_handler import update_player_name_if_changed
import threading
import requests

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",)
        
    def clean_username(self):
        username = self.cleaned_data.get("username")
        
        import re
        if not re.match(r'^[a-zA-Z0-9_]{3,16}$', username):
            raise forms.ValidationError("Никнейм может содержать только английские буквы, цифры, нижнее подчеркивание и быть от 3 до 16 символов длиной.")
        
        if User.objects.filter(username=username).exists():
            player = Player.objects.filter(nickname=username).first()
            if player and player.uuid:
                try:
                    changed = update_player_name_if_changed(player)
                    if changed:
                        return username
                    else:
                        raise forms.ValidationError("Пользователь с таким ником уже существует.")
                except requests.exceptions.RequestException:
                    def retry_update(p):
                        try:
                            update_player_name_if_changed(p)
                        except:
                            pass
                    
                    threading.Thread(target=retry_update, args=(player,), daemon=True).start()
                    raise forms.ValidationError("Пожалуйста, подождите пару минут и попробуйте отправить форму снова (связь с API).")
            
            raise forms.ValidationError("Пользователь с таким ником уже существует.")
            
        return username
