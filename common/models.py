from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.fields import ArrayField, JSONField
from django.core.validators import RegexValidator, EmailValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.conf import settings


LOGIN_SUCCESS = 0
LOGIN_NOT_EXIST = 1
LOGIN_NOT_MATCH = 2
LOGIN_DEACTIVATED = 3
LOGIN_ATTEMPT_COUNT_EXCEEDED = 9
LOGIN_ATTEMPT_COUNT_RESET = -1

LOGIN_ATTEMPT_RESULTS = [
    (LOGIN_SUCCESS, _('Success')),
    (LOGIN_NOT_EXIST, _('Not exist')),
    (LOGIN_NOT_MATCH, _('Not match')),
    (LOGIN_ATTEMPT_COUNT_EXCEEDED, _('Attempt count exceeded')),
    (LOGIN_ATTEMPT_COUNT_RESET, _('Attempt count reset')),
]


class BaseUserLoginAttemptManager(models.Manager):
    """
    Manager for User's Login Attempt Information
    """
    def get_failed_count(self, user_id):
        last_success = self.filter(
            user_id=user_id,
            result__in=[LOGIN_SUCCESS, LOGIN_ATTEMPT_COUNT_RESET]
        ).order_by('id').last()
        login_failed = self.filter(user_id=user_id)\
            .exclude(result__in=[LOGIN_SUCCESS, LOGIN_ATTEMPT_COUNT_RESET])
        if last_success:
            login_failed = login_failed.filter(id__gt=last_success.id)
        return login_failed.count()

    def reset_failed_count(self, user_id):
        self.create(
            user_id=user_id,
            result=LOGIN_ATTEMPT_COUNT_RESET,
            device_info={},
            app_info={}
        )


class BaseUserLoginAttemptModel(models.Model):
    """
    User's Login Attempt Information
    """
    user_id = models.CharField(_('User ID'), max_length=100, blank=True, default='')
    device_info = JSONField(_('Device Info'), default=dict)
    app_info = JSONField(_('App Info'), default=dict)
    result = models.SmallIntegerField(_('Result'), choices=LOGIN_ATTEMPT_RESULTS)
    attempted_datetime = models.DateTimeField(_('Attempted Datetime'), auto_now_add=True)

    objects = BaseUserLoginAttemptManager()

    class Meta:
        verbose_name = _('User Login Attempt')
        verbose_name_plural = _('User Login Attempts')
        abstract = True


class DefaultEmailUserManager(BaseUserManager):
    """
    Default Email User Manager
	"""

    def _create_user(self, email, password, **extra_fields):
        now = timezone.now()
        if not email:
            raise ValueError(_('Enter a email address.'))
        email = self.normalize_email(email)
        if 'name' in extra_fields:
            extra_fields['name'] = self.model.normalize_username(extra_fields['name'])
        user = self.model(email=email, is_active=True, created_datetime=now, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class DefaultEmailUserModel(AbstractBaseUser, PermissionsMixin):
    """
    Default Email User Model
    """
    username = models.CharField(_('Name'), blank=True, default='', max_length=12)
    email = models.EmailField(_('Email'), max_length=100, unique=True)
    created_datetime = models.DateTimeField(_('Joined Datetime'), auto_now_add=True)
    is_staff = models.BooleanField(_('Is Staff'), default=False)
    is_active = models.BooleanField(_('Is Active'), default=True)

    objects = DefaultEmailUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    LOGIN_ATTEMPT_MODEL = BaseUserLoginAttemptModel

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        abstract = True

    def __str__(self):
        return self.username or self.email

    def get_short_name(self):
        return self.username

    def get_full_name(self):
        return self.username

    @property
    def login_attempts(self):
        return self.LOGIN_ATTEMPT_MODEL.objects.filter(user_id=self.email)

    @property
    def login_failed(self):
        return self.login_attempts.exclude(result=LOGIN_SUCCESS)

    @property
    def login_succeeded(self):
        return self.login_attempts.filter(result=LOGIN_SUCCESS)

    @property
    def last_login_succeeded(self):
        return self.login_attempts.filter(result=LOGIN_SUCCESS).last()

    @property
    def device_info(self):
        return self.last_login_succeeded.device_info if self.last_login_succeeded else {}

    @property
    def app_info(self):
        return self.last_login_succeeded.app_info if self.last_login_succeeded else {}

