from django.core.management.base import BaseCommand
from django.utils import timezone
from prison.utils import generate_all_notifications


class Command(BaseCommand):
    help = 'Generate notifications for medical checkups, upcoming releases, and new admissions'

    def handle(self, *args, **options):
        self.stdout.write('Generating notifications...')
        
        try:
            results = generate_all_notifications()
            
            self.stdout.write(self.style.SUCCESS(
                f'Successfully generated notifications:\n'
                f'  - Medical checkup notifications: {results["medical_checkup_notifications"]}\n'
                f'  - Near release notifications: {results["near_release_notifications"]}\n'
                f'  - Total notifications: {results["total"]}'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error generating notifications: {str(e)}'))
            raise