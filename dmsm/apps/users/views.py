from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.views import View
from django.conf import settings
from django.core.signing import loads, SignatureExpired, BadSignature
from django.contrib import messages
from django.contrib.auth.models import User
from dmsm.apps.users.models import UserProfile
from dmsm.apps.core.models import Player, Server, Session
from dmsm.apps.users.forms import CustomUserCreationForm

class RegisterView(View):
    def get(self, request):
        
        nickname = request.GET.get('nickname', '')
        if nickname and not request.session.get(nickname):
            return redirect('users:register')
            
        form = CustomUserCreationForm()
        if nickname:
            form.initial['username'] = nickname
            form.fields['username'].widget.attrs['readonly'] = True
            
        return render(request, 'users/register.html', {'form': form, 'nickname': nickname})

    def post(self, request):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            
            is_linked = False
            if request.session.get(user.username):
                player = Player.objects.filter(nickname=user.username).first()
                if player:
                    profile.player = player
                    profile.save()
                    is_linked = True
                del request.session[user.username]
            
            whitelist_mode = getattr(settings, 'WHITELIST_MODE', False)
            if whitelist_mode:
                profile.is_pending_whitelist = True
                profile.save()
                
            login(request, user)
            
            return render(request, 'users/register.html', {
                'success': True,
                'whitelist_mode': whitelist_mode,
                'is_linked': is_linked,
                'username': user.username
            })
        username = request.POST.get('username', '')
        if username and request.session.get(username):
            form.fields['username'].widget.attrs['readonly'] = True
            
        return render(request, 'users/register.html', {'form': form})

class LoginView(View):
    def get(self, request):
        nickname = request.GET.get('nickname', '')
        if nickname and not request.session.get(nickname):
            return redirect('users:login')
            
        form = AuthenticationForm(initial={'username': nickname} if nickname else None)
        if nickname:
            form.fields['username'].widget.attrs['readonly'] = True
            
        can_reset = request.session.get(nickname, False) if nickname else False
        return render(request, 'users/login.html', {'form': form, 'nickname': nickname, 'can_reset': can_reset})

    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            if request.session.get(user.username):
                profile, _ = UserProfile.objects.get_or_create(user=user)
                linked_now = False
                if not profile.player:
                    player = Player.objects.filter(nickname=user.username).first()
                    if player:
                        profile.player = player
                        profile.save()
                        linked_now = True
                del request.session[user.username]
                
                if linked_now:
                    messages.success(request, f"С возвращением, {user.username}! Ваш профиль успешно привязан.")
                else:
                    messages.success(request, f"С возвращением, {user.username}!")
            else:
                messages.success(request, f"С возвращением, {user.username}!")
                
            return redirect('/')
            
        username = request.POST.get('username', '')
        if username and request.session.get(username):
            form.fields['username'].widget.attrs['readonly'] = True
            
        can_reset = request.session.get(username, False)
        return render(request, 'users/login.html', {'form': form, 'can_reset': can_reset, 'nickname': username})

class LinkProfileView(View):
    def get(self, request, token):
        try:
            data = loads(token, max_age=3600)
        except SignatureExpired:
            messages.error(request, "Срок действия ссылки истек. Введите /trigger link еще раз.")
            return redirect('/')
        except BadSignature:
            messages.error(request, "Недействительная ссылка.")
            return redirect('/')

        nickname = data.get('nickname')
        
        player = Player.objects.filter(nickname=nickname).first()
        if not player:
            messages.error(request, "Игровой профиль не найден. Попробуйте еще раз.")
            return redirect('/')

        request.session[nickname] = True
        existing_user = User.objects.filter(username=nickname).first()
        
        if existing_user:
            if not request.user.is_authenticated:
                return redirect(f'/users/login/?nickname={nickname}')
            else:
                if request.user == existing_user:
                    profile, _ = UserProfile.objects.get_or_create(user=request.user)
                    if profile.player == player:
                        messages.info(request, f"Ваш профиль уже привязан к аккаунту {nickname}.")
                    else:
                        profile.player = player
                        profile.save()
                        messages.success(request, f"Профиль {nickname} успешно привязан!")
                    
                    if nickname in request.session:
                        del request.session[nickname]
                    return redirect('/')
                else:
                    messages.error(request, f"Вы авторизованы как {request.user.username}, но ссылка принадлежит {nickname}. Пожалуйста, перезайдите в нужный аккаунт.")
                    return redirect('/')
        else:
            if not request.user.is_authenticated:
                return redirect(f'/users/register/?nickname={nickname}')
            else:
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                if profile.player == player:
                    messages.info(request, f"Ваш профиль уже привязан к аккаунту {nickname}.")
                else:
                    profile.player = player
                    profile.save()
                    messages.success(request, f"Профиль {nickname} успешно привязан к аккаунту {request.user.username}!")
                
                if nickname in request.session:
                    del request.session[nickname]
                return redirect('/')

class ResetPasswordView(View):
    def get(self, request):
        nickname = request.GET.get('nickname')
        if not nickname or not request.session.get(nickname):
            messages.error(request, "У вас нет прав для сброса пароля. Перейдите по актуальной ссылке из игры.")
            return redirect('/')
            
        user = User.objects.filter(username=nickname).first()
        if not user:
            messages.error(request, "Пользователь не найден.")
            return redirect('/')
            
        form = SetPasswordForm(user)
        return render(request, 'users/reset_password.html', {'form': form, 'nickname': nickname})
        
    def post(self, request):
        nickname = request.POST.get('nickname')
        if not nickname or not request.session.get(nickname):
            messages.error(request, "У вас нет прав для сброса пароля. Перейдите по актуальной ссылке из игры.")
            return redirect('/')
            
        user = User.objects.filter(username=nickname).first()
        if not user:
            messages.error(request, "Пользователь не найден.")
            return redirect('/')
            
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            user = form.save()
            
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.player:
                player = Player.objects.filter(nickname=nickname).first()
                if player:
                    profile.player = player
                    profile.save()
                    
            del request.session[nickname]
            
            login(request, user)
            messages.success(request, f"С возвращением, {user.username}! Пароль успешно изменен.")
            return redirect('/')
            
        return render(request, 'users/reset_password.html', {'form': form, 'nickname': nickname})

class UserProfileView(View):
    def get(self, request, nickname):
        is_own_profile = request.user.is_authenticated and request.user.username == nickname
        
        has_linked_profile = False
        if request.user.is_authenticated:
            req_profile = getattr(request.user, 'userprofile', None)
            has_linked_profile = bool(req_profile and req_profile.player)
            
        if not is_own_profile and not has_linked_profile:
            messages.error(request, "Для просмотра профилей других игроков необходимо авторизоваться и привязать свой игровой аккаунт.")
            return redirect('/')
            
        player = Player.objects.filter(nickname=nickname).first()
        user = User.objects.filter(username=nickname).first()
        
        if not player and not user:
            messages.error(request, "Профиль не найден.")
            return redirect('/')
            
        has_played = player is not None
        
        is_linked = False
        if user:
            profile = getattr(user, 'userprofile', None)
            if profile and profile.player:
                is_linked = True

        player_uuid = player.uuid if player else None
        
        context = {
            'nickname': nickname,
            'is_linked': is_linked,
            'has_played': has_played,
            'is_own_profile': is_own_profile,
            'player_uuid': player_uuid,
            'minecraft_server_ip': getattr(settings, 'MINECRAFT_SERVER_IP', 'play.example.com'),
        }
        return render(request, 'users/profile.html', context)
