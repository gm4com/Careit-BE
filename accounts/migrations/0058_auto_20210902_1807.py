# Generated by Django 2.2.7 on 2021-09-02 18:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0057_user_ci'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='_recommended_by',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='추천인 코드'),
        ),
    ]
