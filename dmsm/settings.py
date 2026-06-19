import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.environ['SECRET_KEY']
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dmsm.apps.monitor',
    'dmsm.apps.core',
    'dmsm.apps.users',
    'dmsm.apps.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'dmsm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'dmsm.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
        'PORT': os.environ['DB_PORT'],
        'CONN_MAX_AGE': 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

PTERODACTYL_URL = os.environ.get('PTERODACTYL_URL')
PTERODACTYL_API_KEY = os.environ.get('PTERODACTYL_API_KEY')
PTERODACTYL_SERVER_ID = os.environ.get('PTERODACTYL_SERVER_ID')

RCON_HOST = os.environ.get('RCON_HOST')
RCON_PORT = os.environ.get('RCON_PORT')
RCON_PASSWORD = os.environ.get('RCON_PASSWORD')
RCON_INTERVAL = int(os.environ.get('RCON_INTERVAL', 5))

WHITELIST_MODE = os.environ.get('WHITELIST_MODE') == 'True'

MODE_FULL = 'full'
MODE_PTERODACTYL_ONLY = 'ptero'
MODE_RCON_ONLY = 'rcon'
MODE_NONE = 'none'

TELLRAW_LINK_MESSAGE = [
    {"text": "<DMSM> Для привязки аккаунта ", "color": "white"},
    {"text": "[перейди по ссылке]", "color": "green", "is_link": True}
]
MINECRAFT_SERVER_IP = os.environ.get('MINECRAFT_SERVER_IP', 'play.example.com')
SITE_URL = os.environ.get('SITE_URL', 'http://127.0.0.1:8000')
STATIC_ROOT = BASE_DIR / 'staticfiles'
