from django.contrib import admin
from .models import Player, Session, Server, Monitor

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
    list_display = ('timestamp', 'is_online', 'player_count')
    list_filter = ('is_online',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)

@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'live_time', 'monitor_mode')
    list_filter = ('monitor_mode',)
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
