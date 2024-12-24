import statistics
import itertools

from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField, JSONField
from django.utils import timezone
from django.apps import apps

from common.models import DefaultEmailUserModel, BaseUserLoginAttemptModel
from common.validators import MobileNumberOnlyValidators
from base.models import Area, BannedWord
from base.constants import *

from accounts.models import User
from missions.models import Mission


class UserAsIs(models.Model):
    """
    1.0 uid 마이그레이션용 모델
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='user_uid', on_delete=models.CASCADE)
    uid = models.CharField('UID', max_length=10, unique=True)


class HelperAsIs(models.Model):
    """
    1.0 h_uid 마이그레이션용 모델
    """
    user = models.ForeignKey(User, verbose_name='회원', related_name='user_h_uid', on_delete=models.CASCADE)
    h_uid = models.CharField('H_UID', max_length=10, unique=True)


# class AnycodeAsIs(models.Model):
#     """
#     미션 입찰 모델
#     """
#     mission = models.ForeignKey(Mission, verbose_name='미션', related_name='missions_anycode', on_delete=models.CASCADE)
#     # user = models.ForeignKey(User, verbose_name='회원', related_name='mission_user_h_uid', on_delete=models.CASCADE, default=User.DE)
#     anycode = models.CharField('AnyCode', max_length=10)


class MissionAsIs(models.Model):
    """
    미션 입찰 모델
    """
    mission = models.ForeignKey(Mission, verbose_name='미션', related_name='mission_anycode', on_delete=models.CASCADE)
    user = models.ForeignKey(User, verbose_name='회원', related_name='mission_user_h_uid', on_delete=models.CASCADE)
    anycode = models.CharField('AnyCode', max_length=10)
