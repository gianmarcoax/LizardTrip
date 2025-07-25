# Generated by Django 4.2.7 on 2025-07-06 02:08

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Bus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('placa', models.CharField(max_length=10, unique=True)),
                ('activo', models.BooleanField(default=True)),
                ('conductor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Ruta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('origen', models.CharField(max_length=200)),
                ('destino', models.CharField(max_length=200)),
                ('color', models.CharField(default='#FF0000', max_length=7)),
                ('activa', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='UbicacionBus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('latitud', models.DecimalField(decimal_places=8, max_digits=10)),
                ('longitud', models.DecimalField(decimal_places=8, max_digits=11)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('bus', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracker.bus')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='Paradero',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('latitud', models.DecimalField(decimal_places=8, max_digits=10)),
                ('longitud', models.DecimalField(decimal_places=8, max_digits=11)),
                ('orden', models.IntegerField()),
                ('ruta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracker.ruta')),
            ],
            options={
                'ordering': ['orden'],
            },
        ),
        migrations.CreateModel(
            name='Horario',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hora_salida', models.TimeField()),
                ('tipo', models.CharField(choices=[('mañana', 'Mañana'), ('mediodia', 'Mediodía'), ('tarde', 'Tarde')], max_length=20)),
                ('activo', models.BooleanField(default=True)),
                ('ruta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tracker.ruta')),
            ],
        ),
        migrations.AddField(
            model_name='bus',
            name='ruta_actual',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='tracker.ruta'),
        ),
    ]
