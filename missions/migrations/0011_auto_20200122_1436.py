# Generated by Django 2.2.7 on 2020-01-22 05:36

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('missions', '0010_auto_20200121_1128'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mission',
            name='address_book',
        ),
        migrations.AddField(
            model_name='address',
            name='name',
            field=models.CharField(blank=True, default='', max_length=8, verbose_name='별칭'),
        ),
        migrations.AddField(
            model_name='address',
            name='user',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, related_name='address_books', to=settings.AUTH_USER_MODEL, verbose_name='회원'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='mission',
            name='final_address',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='final_address_missions', to='missions.Address', verbose_name='최종 목적지'),
        ),
        migrations.AddField(
            model_name='mission',
            name='stopovers',
            field=models.ManyToManyField(blank=True, related_name='stopover_missions', to='missions.Address', verbose_name='경유지'),
        ),
        migrations.DeleteModel(
            name='AddressBook',
        ),
    ]