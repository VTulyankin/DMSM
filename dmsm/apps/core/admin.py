from django.contrib import admin
from .models import Player, Session, Server

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'uuid', 'first_seen')
    search_fields = ('nickname', 'uuid')

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('player', 'login_time', 'logout_time')
    search_fields = ('player__nickname',)
    list_filter = ('login_time',)

@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'is_online', 'player_count', 'service_mode')
    list_filter = ('is_online', 'service_mode')
