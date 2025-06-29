# Generated by Django 5.1.7 on 2025-06-16 10:06

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('common', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=100)),
                ('slug', models.SlugField(unique=True)),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hr.department')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Staff',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('full_name', models.CharField(max_length=150)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('gender', models.CharField(choices=[('Male', 'Male'), ('Female', 'Female')], max_length=10)),
                ('birth_date', models.DateField(blank=True, null=True)),
                ('salary', models.DecimalField(decimal_places=2, max_digits=12)),
                ('hire_date', models.DateField()),
                ('exit_date', models.DateField(blank=True, null=True)),
                ('grade', models.CharField(blank=True, choices=[('associate', 'Associate'), ('graduate_trainee', 'Graduate Trainee'), ('management_trainee', 'Management Trainee'), ('junior_assistant', 'Junior Assistant'), ('senior_manager', 'Senior Manager')], max_length=50, null=True)),
                ('department', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='hr.department')),
                ('district', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.businessdistrict')),
                ('role', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='hr.role')),
                ('state', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='common.state')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
