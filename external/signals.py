from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.urls import reverse
from django.conf import settings

from common.utils import SlackWebhook, get_md5_hash
from notification.models import Notification
from .models import ExternalMission



@receiver(pre_save, sender=ExternalMission)
def make_external_mission_login_code(sender, instance, **kwargs):
    if instance.login_code == '':
        code = str(timezone.now().timestamp())
        while True:
            instance.login_code = get_md5_hash(code)
            if not sender.objects.filter(login_code=instance.login_code).exists():
                break
            code += str(instance.user_id)


@receiver(post_save, sender=ExternalMission)
def handle_external_mission(sender, instance, **kwargs):
    # 미션등록 성공 sms
    Notification.objects.sms_preset(instance.user, 'external_requested', args=[instance.shortened_url])

    # 이케아 알림 처리
    # if instance.mission_type.code == 'IK' \
    #         and 'IK' in settings.SLACK_EXTERNAL_MISSIONS \
    #         and settings.SLACK_EXTERNAL_MISSIONS['IK']:
    #     url = 'https://%s%s' % (settings.MAIN_HOST, reverse('admin:external_externalmission_change',
    #                                                         kwargs={'object_id': instance.id}))
    #     slack = SlackWebhook().channel(settings.SLACK_EXTERNAL_MISSIONS['IK'])
    #     slack.script_msg('이케아 미션요청 알림', '새로운 이케아 미션요청이 있습니다.\n%s' % url, )
