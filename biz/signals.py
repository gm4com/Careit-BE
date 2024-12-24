import random

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from base.constants import USER_CODE_STRINGS
from .models import Partnership, Campaign


@receiver(pre_save, sender=Campaign)
def make_campaign_code(sender, instance, **kwargs):
    if not instance.campaign_code:
        while True:
            campaign_code = ''.join(random.sample(USER_CODE_STRINGS, 5))
            if not sender.objects.filter(campaign_code=campaign_code).exists():
                break
        instance.campaign_code = campaign_code
