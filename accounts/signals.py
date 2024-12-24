import random

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.urls import reverse

from django_rest_passwordreset.signals import reset_password_token_created, post_password_reset

from common.utils import get_random_digit
from common.models import LOGIN_ATTEMPT_COUNT_RESET
from base.constants import USER_CODE_STRINGS
from notification.models import Notification
from .models import User, MobileVerification
from .views import reset_password_token_created_by_mobile


@receiver(pre_save, sender=User)
def make_user_code(sender, instance, **kwargs):
    if not instance.code:
        while True:
            code = ''.join(random.sample(USER_CODE_STRINGS, 5))
            if not sender.objects.filter(code=code).exists():
                break
        instance.code = code


@receiver(pre_save, sender=MobileVerification)
def make_verification_code(sender, instance, **kwargs):
    if not instance.nice_data and not instance.verified_datetime:
        instance.code = get_random_digit(6)
        Notification.objects.sms(instance.number, '[애니맨 인증코드]\n귀하의 인증코드는 [%s]입니다.' % instance.code)


@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    context = {
        'current_user': reset_password_token.user,
        'username': reset_password_token.user.username,
        'email': reset_password_token.user.email,
        'code': reset_password_token.key,
        'reset_password_url': "{}?token={}".format(reverse('reset-password-request'), reset_password_token.key)
    }
    Notification.objects.email_preset(reset_password_token.user, 'password_reset_requested', context=context)


@receiver(reset_password_token_created_by_mobile)
def password_reset_token_created_by_mobile(sender, instance, reset_password_token, mobile_number, *args, **kwargs):
    Notification.objects.sms(mobile_number, '[애니맨 인증코드]\n귀하의 인증코드는 [%s]입니다.' % reset_password_token.key)


@receiver(post_password_reset)
def login_attempt_count_reset(sender, **kwargs):
    if 'user' in kwargs and kwargs['user']:
        User.LOGIN_ATTEMPT_MODEL.objects.reset_failed_count(kwargs['user'].mobile)
        if kwargs['user'].email:
            User.LOGIN_ATTEMPT_MODEL.objects.reset_failed_count(kwargs['user'].email)
