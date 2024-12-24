import random

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from common.utils import get_random_digit
from common.utils import SlackWebhook
from notification.models import Notification, Tasker
from payment.models import Cash, Point, Reward
from .utils import KeywordWarning
from .models import MultiMission, Mission, Bid, MissionWarningNotice, Review, SafetyNumber


keyword_warning = KeywordWarning()


@receiver(pre_save, sender=MultiMission)
@receiver(pre_save, sender=Mission)
def make_mission_code(sender, instance, **kwargs):
    if not instance.code:
        if instance.mission_type.id == 1:
            suffix = str((sender.objects.filter(user=instance.user).count() + 1) % 100)
            code = 'U' + instance.user.code + suffix
        else:
            # 기업 미션
            suffix = str(int(timezone.now().timestamp()))[-6:]
            code = instance.mission_type.code + suffix
        instance.code = code


@receiver(post_save, sender=Bid)
def safety_number(sender, instance, **kwargs):
    if instance.state == 'in_action' and not instance.customer_safety_number:
        SafetyNumber.objects.assign_pair_from_bid(instance)


@receiver(post_save, sender=Review)
def reviewed_send_push(sender, instance, **kwargs):
    # 새 db에서 발생한 리뷰만 푸쉬를 발송함.
    if instance.bid_id and kwargs['created'] and instance.is_active:
        preset = 'reviewed_from_helper' if instance.is_created_user_helper else 'reviewed_from_customer'
        # Notification.objects.push_preset(instance.received_user, preset, args=[instance.created_user.username])
        Tasker.objects.task(preset, user=instance.received_user, kwargs={
            'sender': instance.created_user.username,
            'stars': '  '.join(instance.star_text)
        })


@receiver(pre_save, sender=Review)
def reviewed_handle_reward(sender, instance, **kwargs):
    # computed field 계산
    instance._received_user = instance.received_user

    if instance.bid_id:
        instance._is_created_user_helper = instance.is_created_user_helper

        # 리워드 관련 처리
        # - 새 db에서 발생한 것만 리워드 가감이 일어남.
        # - 리뷰를 직접 입력한 경우 가감하지 않음

        # 고객/헬퍼에 따른 리워드 종류 결정
        if instance.is_created_user_helper:
            reward_type = 'helper_created_review'
            model = Cash
            field = 'cash'
            kwargs = {'helper': instance.bid.helper}
        else:
            reward_type = 'customer_created_review'
            model = Point
            field = 'point'
            kwargs = {'user': instance.created_user}

        if not instance.pk:
            # 리뷰 작성됐을 때
            instance.reward = Reward.objects.get_active(reward_type)
            if instance.reward:
                kwargs.update({'amount': instance.reward.calculate_reward(instance.bid.customer_paid)})
                setattr(instance, field, model.objects.create(**kwargs))

        elif not instance.is_active:
            # 리뷰 삭제됐을 때
            rewarded_obj = getattr(instance, field, None)
            if rewarded_obj:
                rewarded_obj.amount = -rewarded_obj.amount
                rewarded_obj.save()
                rewarded_obj.amount = 0
                rewarded_obj.save()


@receiver(post_save, sender=MissionWarningNotice)
def refresh_warning_cache(sender, instance, **kwargs):
    keyword_warning.refresh()
