from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'is_linked', 'is_staff', 'is_superuser')
    
    def is_linked(self, obj):
        profile = getattr(obj, 'userprofile', None)
        return bool(profile and profile.player)
    
    is_linked.short_description = 'Статус привязки'
    is_linked.boolean = True
