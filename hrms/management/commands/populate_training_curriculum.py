"""Creates the Correctional Officers' Basic Training Curriculum courses."""

from django.core.management.base import BaseCommand
from django.db import transaction

from hrms.models import TrainingCourse


class Command(BaseCommand):
    help = (
        "Creates or updates a TrainingCourse for every subject in the standard "
        "Correctional Officers' Basic Training Curriculum."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--total-marks',
            type=int,
            default=100,
            help='Total marks for each created course (default: 100).',
        )
        parser.add_argument(
            '--passing-mark',
            type=int,
            default=50,
            help='Passing mark for each created course (default: 50).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        total_marks = options['total_marks']
        passing_mark = options['passing_mark']

        if passing_mark > total_marks:
            self.stderr.write(
                self.style.ERROR('Passing mark cannot exceed the total marks.')
            )
            return

        created = 0
        updated = 0

        for order, (course_code, course_name) in enumerate(
            TrainingCourse.COURSE_CHOICES, start=1
        ):
            course, was_created = TrainingCourse.objects.get_or_create(
                course_code=course_code,
                defaults={
                    'name': course_name,
                    'total_marks': total_marks,
                    'passing_mark': passing_mark,
                    'display_order': order,
                    'is_required': True,
                    'is_active': True,
                },
            )

            if was_created:
                created += 1
                continue

            course.name = course_name
            course.display_order = order
            course.save()
            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Curriculum ready: {created} course(s) created, '
                f'{updated} course(s) refreshed.'
            )
        )
