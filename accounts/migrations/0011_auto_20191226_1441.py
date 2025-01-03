# Generated by Django 2.2.7 on 2019-12-26 05:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0010_auto_20191224_0953'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceBlock',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(verbose_name='사유')),
                ('start_datetime', models.DateTimeField(auto_now_add=True, verbose_name='시작일시')),
                ('end_datetime', models.DateTimeField(blank=True, null=True, verbose_name='종료일시')),
            ],
            options={
                'verbose_name': '서비스 블록',
                'verbose_name_plural': '서비스 블록',
            },
        ),
        migrations.RemoveField(
            model_name='user',
            name='_is_blocked',
        ),
        migrations.AddField(
            model_name='user',
            name='_is_service_blocked',
            field=models.BooleanField(blank=True, default=False, null=True, verbose_name='서비스 블록'),
        ),
        migrations.DeleteModel(
            name='Block',
        ),
        migrations.AddField(
            model_name='serviceblock',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='service_blocks', to=settings.AUTH_USER_MODEL, verbose_name='회원'),
        ),
    ]
