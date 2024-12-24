"""
Anyman Server Basic Settings
"""


import os
from _datetime import timedelta


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEBUG = True


# Host settings

ALLOWED_HOSTS = []
MAIN_HOST = 'w.anyman.co.kr'
SHORTEN_HOST = 'w.anyman.co.kr'
STATIC_HOST = 'www.anyman.co.kr'


# Application definition

INSTALLED_APPS = [
    'common',
    'django_extensions',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'corsheaders',
    'admin_reorder',
    'rest_framework',
    'django_rest_passwordreset',
    'drf_yasg',
    'rest_framework.authtoken',
    'django_summernote',
    'base',
    'accounts',
    'missions',
    'external',
    'notification',
    'payment',
    'board',
    'anyman_migration',
    'biz',
]

SITE_ID = 1

# GOOGLE_ANALYTICS_UA = ''

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'admin_reorder.middleware.ModelAdminReorder',
]

ROOT_URLCONF = 'web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates'), ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'common.context_processors.template_load_settings',
            ],
        },
    },
]

TEMPLATE_LOAD_SETTINGS = (
    # 'GOOGLE_ANALYTICS_UA',
)

WSGI_APPLICATION = 'web.wsgi.application'


# Authentication

AUTH_USER_MODEL = 'accounts.User'

AUTHENTICATION_BACKENDS = [
    # 'django.contrib.auth.backends.ModelBackend',
    'accounts.backends.EmailBackend',
]

LOGIN_URL = 'rest_framework:login'

LOGOUT_URL = 'rest_framework:logout'

LOGIN_REDIRECT_URL = '/'

LOGOUT_REDIRECT_URL = '/'

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

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        # 'rest_framework.authentication.SessionAuthentication',
        'common.context_processors.CsrfExemptSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'base.pagination.Pagination',
    'PAGE_SIZE': 15
}

REST_USE_JWT = True

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    # 'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    # 'REFRESH_TOKEN_LIFETIME': timedelta(minutes=3),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,

    'ALGORITHM': 'HS256',
    # 'SIGNING_KEY': settings.SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'id',
    # 'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    # 'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    # 'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    # 'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

DJANGO_REST_PASSWORDRESET_TOKEN_CONFIG = {
    "CLASS": "django_rest_passwordreset.tokens.RandomNumberTokenGenerator",
    "OPTIONS": {
        "min_number": 100000,
        "max_number": 999999
    }
}


SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'api_key': {
            'type': 'apiKey',
            'in': 'header',
            'name': 'Authorization'
        }
    },
}


EXTERNAL_MISSION_SMS_URLS = {
    'IK': 'https://assembly.anyman.co.kr/ikea_mission.html'
}

WEB_MISSION_DETAIL_URL = 'https://www.anyman.co.kr/proceed/'


# Internationalization

LANGUAGE_CODE = 'ko'

TIME_ZONE = 'Asia/Seoul'

USE_I18N = True

USE_L10N = True

USE_TZ = False

LOCALE_PATHS = ['web/conf/locale']


# Static files (CSS, JavaScript, Images)

STATIC_URL = '/static/'

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

STATICFILES_DIRS =(
	os.path.join(BASE_DIR, 'common/staticfiles'),
    os.path.join(BASE_DIR, 'biz/staticfiles'),
)


# Media files

MEDIA_URL = '/media/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

FILE_UPLOAD_PERMISSIONS = 0o644

DATA_UPLOAD_MAX_MEMORY_SIZE = 26214400
FILE_UPLOAD_MAX_MEMORY_SIZE = 26214400


# summernote

def summernote_upload_admin_only(request):
    return request.user.is_staff

SUMMERNOTE_THEME = 'bs4'

SUMMERNOTE_CONFIG = {
    'iframe': False,

    'summernote': {
        'airMode': False,
        'width': '100%',
        # 'height': '480',
        'lang': 'ko-KR',
        'codemirror': {
            'mode': 'htmlmixed',
            'lineNumbers': 'true',
            'theme': 'monokai',
        },
        'toolbar': [
            ['style', ['style']],
            ['font', ['bold', 'italic', 'underline', 'strikethrough', 'superscript', 'subscript', 'clear']],
            # ['fontname', ['fontname']],
            ['fontsize', ['fontsize']],
            ['color', ['color']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['height', ['height']],
            ['table', ['table']],
            ['insert', ['link', 'picture', 'video']],
            ['view', ['fullscreen', 'codeview']],

        ]
    },
    'attachment_filesize_limit': 64000000,
    'attachment_require_authentication': True,
    # 'attachment_upload_to': upload_to_func(),
    # 'attachment_storage_class': 'storage.name',
    'disable_attachment': False,
    'attachment_absolute_uri': False,
    'test_func_upload_view': summernote_upload_admin_only,
    'css': (
        '//cdnjs.cloudflare.com/ajax/libs/codemirror/5.29.0/theme/monokai.min.css',
    ),
    'lazy': False,
}


# Admin

ADMINS = [
	('Soo', 'soo@haru.ltd'),
]

ADMIN_SITE_HEADER = 'Anyman Admin'

ADMIN_DELETE_ACTION_DEFAULT = False

ADMIN_REORDER = (
    {
        'app': 'accounts',
        'models': (
            'accounts.User',
            'accounts.Helper',
            'accounts.ServiceBlock',
            'accounts.ServiceTag',
            'auth.Group',
        ),
    },
    {
        'app': 'missions',
        'models': (
            'missions.MultiMission',
            'missions.Mission',
            'missions.Bid',
            'missions.Review',
            'missions.Report',
            'missions.PenaltyPoint',
            'missions.CustomerService',
            'external.ExternalMission'
        )
    },
    {
        'app': 'payment',
        'models': (
            'payment.Payment',
            'payment.Billing',
            'payment.PointVoucherTemplate',
            'payment.CouponTemplate',
            'payment.Point',
            'payment.Cash',
            'payment.Withdraw',
        )
    },
    {
        'app': 'board',
        'models': (
            'board.ContactWriting',
            'board.PartnershipWriting',
            'board.NoticeWriting',
            'board.EventWriting',
            'board.MagazineWriting',
            'board.WebtoonWriting',
            'board.FAQWriting',
            'board.ArticleWriting',
        )
    },
    {
        'app': 'base',
        'label': '내부 컨텐츠',
        'models': (
            'base.Popup',
            'base.Area',
            'missions.MissionWarningNotice',
            'base.BannedWord',
            'accounts.Agreement',
            'accounts.Quiz',
            'payment.Reward',
            'missions.MissionType',
            'missions.TemplateCategory',
            'missions.TemplateTag',
            'missions.MissionTemplate',
        ),
    },
    {
        'app': 'admin',
        'models': (
            # 'sites.Site',
            'notification.ReceiverGroup',
            'notification.Tasker',
            'notification.Notification',
            'missions.SafetyNumber',
            'accounts.LoggedInDevice',
            # {
            #     'model': 'authtoken.Token',
            #     'label': '토큰',
            # },
            'admin.LogEntry',
        )
    },
    {
        'app': 'biz',
        'label': '애니비즈',
        'models': (
            'biz.Partnership',
            'biz.Campaign',
        )
    }
)


# Cache

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_default',
        'TIMEOUT': 60,
    }
}


# Additional settings

SERVER_DEPLOY_NAME = os.getenv('SERVER_DEPLOY_NAME', None)
if SERVER_DEPLOY_NAME == 'production':
    from web.settings_production import *
elif SERVER_DEPLOY_NAME == 'staging':
    from web.settings_staging import *
elif SERVER_DEPLOY_NAME == 'relay':
    from web.settings_relay import *
else:
    from web.settings_local import *
    INSTALLED_APPS = LOCAL_INSTALLED_APPS + INSTALLED_APPS
    MIDDLEWARE = MIDDLEWARE + LOCAL_MIDDLEWARE


SIMPLE_JWT['SIGNING_KEY'] = SECRET_KEY
