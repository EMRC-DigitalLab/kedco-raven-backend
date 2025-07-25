# Generated by Django 5.1.7 on 2025-06-16 10:06

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Band',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True)),
                ('slug', models.SlugField(blank=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='BusinessDistrict',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(blank=True, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='InjectionSubstation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(blank=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Feeder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('voltage_level', models.CharField(choices=[('11kv', '11kV'), ('33kv', '33kV')], max_length=10)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('band', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.band')),
                ('business_district', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='feeders', to='common.businessdistrict')),
                ('substation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='feeders', to='common.injectionsubstation')),
            ],
            options={
                'unique_together': {('name', 'substation')},
            },
        ),
        migrations.AddField(
            model_name='businessdistrict',
            name='state',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='districts', to='common.state'),
        ),
        migrations.CreateModel(
            name='DistributionTransformer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(blank=True, unique=True)),
                ('feeder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transformers', to='common.feeder')),
            ],
            options={
                'unique_together': {('name', 'feeder')},
            },
        ),
        migrations.AlterUniqueTogether(
            name='businessdistrict',
            unique_together={('name', 'state')},
        ),
    ]
