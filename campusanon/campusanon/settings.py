"""
Django settings for campusanon project.
Updated for Production: Env vars, Security, CORS, Logging.
"""

import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# =================================================
# 🔐 1. & 4. SECRET KEY & DEBUG
# =================================================
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-fallback-dev-key')

# 🔒 2. Turn DEBUG OFF in production
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# 🌍 3. ALLOWED_HOSTS
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third Party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',  # 🌐 8. CORS

    # Local Apps
    'accounts',
    'communities',
    'posts',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # 🌐 8. CORS (Must be at the top)
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'campusanon.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'campusanon.wsgi.application'


# =================================================
# 🗄️ 5. DATABASE (PostgreSQL)
# =================================================
# Reads DATABASE_URL from .env
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        # 👇 CHANGE THIS LINE
        # This checks for a specific env variable. If it's missing, it defaults to False.
        ssl_require=os.getenv('DB_SSL_MODE') == 'True' 
    )
}

# =================================================
# 🌐 8. CORS (Frontend Access)
# =================================================
# In production, specify your frontend domain explicitly
# CORS_ALLOWED_ORIGINS = [
#     "http://localhost:5173",  # React Local Dev
#     "https://yourfrontend.com",
# ]

CORS_ALLOW_ALL_ORIGINS = True

# If you just want to allow everything during dev (NOT RECOMMENDED FOR PROD):
# CORS_ALLOW_ALL_ORIGINS = DEBUG


# =================================================
# 🔐 7. JWT HARDENING
# =================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_MINUTES', 15))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

AUTH_USER_MODEL = "accounts.User"


# =================================================
# ⚡ CACHING (Redis)
# =================================================
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


# =================================================
# 🛡️ 9. SECURITY MIDDLEWARE
# =================================================
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    
    # Cookie Security
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    
    # Redirect HTTP to HTTPS (Enable this only if you have SSL set up)
    # SECURE_SSL_REDIRECT = True 


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# =================================================
# 📦 10. STATIC FILES
# =================================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Required for collectstatic
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# =================================================
# 🔍 11. LOGGING
# =================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Force Django to send emails via Gmail SMTP
import os
# 📧 EMAIL CONFIGURATION
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-relay.brevo.com'
EMAIL_PORT = 2525
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False

# Keep these reading from Environment (Do NOT change these)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER') 
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')

# ⚠️ CRITICAL UPDATE: This must be your VERIFIED Brevo email
DEFAULT_FROM_EMAIL = 'mayurrishi2004@gmail.com'