import django.db.models.deletion
from django.db import migrations, models

REGION_NAMES = {
    'southern': 'Southern Region',
    'northern': 'Northern Region',
    'eastern': 'Eastern Region',
    'central': 'Central Region',
    'western': 'Western Region',
}


def create_regions_from_codes(apps, schema_editor):
    Region = apps.get_model('prison', 'Region')
    PrisonStation = apps.get_model('prison', 'PrisonStation')

    for code, name in REGION_NAMES.items():
        Region.objects.get_or_create(code=code, defaults={'name': name})

    for station in PrisonStation.objects.all():
        code = station.region_code or 'southern'
        region, _ = Region.objects.get_or_create(
            code=code,
            defaults={'name': REGION_NAMES.get(code, code.title())},
        )
        station.region = region
        station.save(update_fields=['region'])


def restore_region_codes(apps, schema_editor):
    PrisonStation = apps.get_model('prison', 'PrisonStation')
    for station in PrisonStation.objects.all():
        station.region_code = station.region.code if station.region else 'southern'
        station.save(update_fields=['region_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('prison', '0009_prisonerreleasereview'),
    ]

    operations = [
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(choices=[('southern', 'Southern Region'), ('northern', 'Northern Region'), ('eastern', 'Eastern Region'), ('central', 'Central Region')], max_length=10, unique=True)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Region',
                'verbose_name_plural': 'Regions',
                'ordering': ['name'],
            },
        ),
        migrations.RenameField(
            model_name='prisonstation',
            old_name='region',
            new_name='region_code',
        ),
        migrations.AddField(
            model_name='prisonstation',
            name='contact_number',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='prisonstation',
            name='region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='stations', to='prison.region'),
        ),
        migrations.RunPython(create_regions_from_codes, restore_region_codes),
        migrations.AlterField(
            model_name='prisonstation',
            name='region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='stations', to='prison.region'),
        ),
        migrations.RemoveField(
            model_name='prisonstation',
            name='region_code',
        ),
    ]
