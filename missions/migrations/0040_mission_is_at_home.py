# Generated by Django 2.2.7 on 2020-04-21 13:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0039_auto_20200417_1502'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='is_at_home',
            field=models.BooleanField(blank=True, default=False, verbose_name='홈 화면 노출여부'),
        ),
    ]
