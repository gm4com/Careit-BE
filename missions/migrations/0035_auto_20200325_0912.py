# Generated by Django 2.2.7 on 2020-03-25 09:12

from django.db import migrations, models
import django_summernote.fields


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0034_auto_20200317_1435'),
    ]

    operations = [
        migrations.AddField(
            model_name='bid',
            name='_canceled_by_admin',
            field=models.BooleanField(blank=True, default=False, verbose_name='직권취소여부'),
        ),
        migrations.AlterField(
            model_name='multimission',
            name='content',
            field=django_summernote.fields.SummernoteTextField(verbose_name='수행내용'),
        ),
    ]