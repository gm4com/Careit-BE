# Generated by Django 2.2.7 on 2019-12-18 01:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_auto_20191212_1103'),
    ]

    operations = [
        migrations.AddField(
            model_name='agreement',
            name='page_code',
            field=models.CharField(default='', max_length=20, verbose_name='페이지코드'),
        ),
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(default='', max_length=100, unique=True, verbose_name='이메일'),
        ),
    ]
