# Generated by Django 2.2.7 on 2019-12-19 04:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_auto_20191219_1012'),
    ]

    operations = [
        migrations.CreateModel(
            name='BannedWord',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('word', models.CharField(max_length=20, verbose_name='단어')),
                ('banned_username', models.BooleanField(blank=True, default=True, verbose_name='회원 닉네임에 적용')),
                ('banned_mission', models.BooleanField(blank=True, default=True, verbose_name='미션 내용에 적용')),
            ],
            options={
                'verbose_name': '금지어',
                'verbose_name_plural': '금지어',
            },
        ),
    ]