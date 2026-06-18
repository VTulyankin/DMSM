from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('v1/stats/online-events/', views.api_online_events, name='api_online_events'),
    path('v1/stats/players-at-time/', views.api_players_at_time, name='api_players_at_time'),
    path('v1/players/<str:nickname>/sessions/', views.api_player_sessions, name='api_player_sessions'),
]
