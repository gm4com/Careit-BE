# Generated by Django 2.2.7 on 2021-03-23 16:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0048_user_is_ad_allowed'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='serviceblock',
            options={'verbose_name': '회원 이용정지 내역', 'verbose_name_plural': '회원 이용정지 내역'},
        ),
    ]
