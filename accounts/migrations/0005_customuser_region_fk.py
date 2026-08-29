import django.db.models.deletion
from django.db import migrations, models


def link_users_to_regions(apps, schema_editor):
    Region = apps.get_model('prison', 'Region')
    CustomUser = apps.get_model('accounts', 'CustomUser')

    for user in CustomUser.objects.exclude(region_code__isnull=True).exclude(region_code=''):
        region = Region.objects.filter(code=user.region_code).first()
        if region:
            user.region = region
            user.save(update_fields=['region'])


def restore_region_codes(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    for user in CustomUser.objects.exclude(region__isnull=True):
        user.region_code = user.region.code
        user.save(update_fields=['region_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_alter_customuser_role'),
        ('prison', '0010_region_prisonstation_region_fk'),
    ]

    operations = [
        migrations.RenameField(
            model_name='customuser',
            old_name='region',
            new_name='region_code',
        ),
        migrations.AddField(
            model_name='customuser',
            name='region',
            field=models.ForeignKey(blank=True, help_text='Region scope, required for regional level roles.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='users', to='prison.region', verbose_name='Assigned Region'),
        ),
        migrations.RunPython(link_users_to_regions, restore_region_codes),
        migrations.RemoveField(
            model_name='customuser',
            name='region_code',
        ),
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.CharField(choices=[('superuser', 'Super Administrator'), ('admin', 'Prison Administrator'), ('reception', 'Reception Officer'), ('officer_in_charge', 'Officer in Charge'), ('station_officer', 'Station Officer'), ('visitor_attendant', 'Visitor Attendant'), ('medical', 'Medical Officer'), ('national_commissioner', 'Commissioner of Administration/HR (National)'), ('national_hr', 'National HR Officer'), ('regional_commanding_officer', 'Region Commanding Officer (RCO)'), ('regional_headquarters_officer', 'Region Headquarters Officer (RHO)'), ('regional_hr', 'Regional HR Officer'), ('station_hr', 'Station HR Officer')], default='reception', max_length=50),
        ),
    ]
