from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_customuser_failed_login_attempts_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customuser',
            name='role',
            field=models.CharField(
                choices=[
                    ('superuser', 'Super Administrator'),
                    ('admin', 'Prison Administrator'),
                    ('reception', 'Reception Officer'),
                    ('officer_in_charge', 'Officer in Charge'),
                    ('station_officer', 'Station Officer'),
                    ('visitor_attendant', 'Visitor Attendant'),
                    ('medical', 'Medical Officer'),
                    ('warden', 'Warden'),
                    ('ict_personnel', 'ICT Personnel'),
                    ('rco', 'Regional Commanding Officer'),
                    ('rho', 'Regional Headquarters Officer'),
                    ('regional_data_control', 'Regional Data Control Officer'),
                ],
                default='reception',
                max_length=30,
            ),
        ),
    ]