# Generated by Django 5.1.6 on 2025-02-25 06:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('BMS_app', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='show',
            unique_together={('show_number', 'movie', 'theatre', 'show_time')},
        ),
    ]
