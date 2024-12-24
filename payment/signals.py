import random

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Point, Cash, PointVoucher


@receiver(pre_save, sender=Point)
@receiver(pre_save, sender=Cash)
def calculate_balance(sender, instance, **kwargs):
    if sender is Point:
        query = {'user': instance.user}
    elif sender is Cash:
        query = {'helper': instance.helper}
    balance = sender.objects.filter(**query).get_balance()
    instance.balance = balance + instance.amount


@receiver(pre_save, sender=PointVoucher)
def set_expire_date_and_code(sender, instance, **kwargs):
    instance.expire_date = timezone.now().date() + timezone.timedelta(days=instance.template.active_days)
    if not instance.code:
        if instance.template.is_repetitive_use:
            instance.code = instance.template.code
        else:
            instance.code = '%s%s' % (
                instance.template.code,
                sender.objects.filter(template_id=instance.template_id).count()
            )
