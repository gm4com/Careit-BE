# Generated by Django 2.2.7 on 2021-02-09 16:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0064_auto_20210209_1519'),
    ]

    operations = [
        migrations.AddField(
            model_name='mission',
            name='login_code',
            field=models.SlugField(blank=True, default='', max_length=32, verbose_name='외부 로그인 코드'),
        ),
    ]