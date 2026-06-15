from dmsm.apps.stats.models import Player

def sync_players(players_dict=None, **kwargs):
    if players_dict is None:
        return
    
    for nickname, uuid in players_dict.items():
        player, created = Player.objects.get_or_create(
            uuid=uuid, 
            defaults={'nickname': nickname}
        )
        
        if not created and player.nickname != nickname:
            player.nickname = nickname
            player.save()
