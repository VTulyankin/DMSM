from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.views import View
from django.conf import settings
from django.core.signing import loads, SignatureExpired, BadSignature
from django.contrib import messages
from django.contrib.auth.models import User
from dmsm.apps.users.models import UserProfile
from dmsm.apps.stats.models import Player, Server
from dmsm.apps.monitor.handler import Handler
from dmsm.apps.monitor.supervisor import Supervisor
from dmsm.apps.monitor.connector import RCONConnector, PterodactylConnector
import threading
import time

def send_one_off_command(cmd):
    handler = Handler()
    supervisor = Supervisor()
    handler.supervisor = supervisor
    
    if supervisor.services['rcon']['has_config']:
        rcon = RCONConnector(handler, supervisor)
        rcon.connect()
        handler.rcon = rcon
        supervisor.update_mode()
        handler.send_command(cmd)
        if rcon.sock:
            rcon.sock.close()
    elif supervisor.services['ptero']['has_config']:
        ptero = PterodactylConnector(handler, supervisor)
        handler.ptero = ptero
        def run_ws():
            ptero.connect()
        t = threading.Thread(target=run_ws, daemon=True)
        t.start()
        time.sleep(1) 
        handler.send_command(cmd)
        if ptero.ws:
            ptero.ws.close()

class RegisterView(View):
    def get(self, request):
        if getattr(settings, 'WHITELIST_MODE', False):
            last_server = Server.objects.last()
            if not last_server or not last_server.is_online:
                return render(request, 'users/registration_closed.html', {'message': 'Сервер недоступен, регистрация временно закрыта.'})
        
        form = UserCreationForm()
        nickname = request.GET.get('nickname', '')
        return render(request, 'users/register.html', {'form': form, 'nickname': nickname})

    def post(self, request):
        if getattr(settings, 'WHITELIST_MODE', False):
            last_server = Server.objects.last()
            if not last_server or not last_server.is_online:
                return render(request, 'users/registration_closed.html', {'message': 'Сервер недоступен, регистрация временно закрыта.'})
                
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            
            if getattr(settings, 'WHITELIST_MODE', False):
                send_one_off_command(f'whitelist add {user.username}')
                
            login(request, user)
            return redirect('/') 
        return render(request, 'users/register.html', {'form': form})

class LoginView(View):
    def get(self, request):
        form = AuthenticationForm()
        nickname = request.GET.get('nickname', '')
        return render(request, 'users/login.html', {'form': form, 'nickname': nickname})

    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('/')
        return render(request, 'users/login.html', {'form': form})

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

        existing_user = User.objects.filter(username=nickname).first()
        
        if existing_user:
            if not request.user.is_authenticated:
                messages.info(request, f"Аккаунт {nickname} уже существует. Войдите, чтобы привязать профиль.")
                return redirect(f'/users/login/?nickname={nickname}')
            else:
                if request.user == existing_user:
                    profile, _ = UserProfile.objects.get_or_create(user=request.user)
                    profile.player = player
                    profile.save()
                    messages.success(request, f"Профиль {nickname} успешно привязан!")
                    return redirect('/')
                else:
                    messages.error(request, f"Вы авторизованы как {request.user.username}, но ссылка принадлежит {nickname}.")
                    return redirect('/')
        else:
            if not request.user.is_authenticated:
                messages.info(request, f"Аккаунт {nickname} не найден. Зарегистрируйтесь.")
                return redirect(f'/users/register/?nickname={nickname}')
            else:
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.player = player
                profile.save()
                messages.success(request, f"Профиль {nickname} успешно привязан к аккаунту {request.user.username}!")
                return redirect('/')
