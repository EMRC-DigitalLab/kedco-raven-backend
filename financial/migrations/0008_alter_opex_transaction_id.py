# Generated by Django 5.1.7 on 2025-07-25 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0007_auto_20250725_1322'),
    ]

    operations = [
        migrations.AlterField(
            model_name='opex',
            name='transaction_id',
            field=models.PositiveIntegerField(help_text='Transaction ID', unique=True),
        ),
    ]
