from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import PrisonStation, Region

from .models import (
    GraduationBatch,
    Officer,
    Rank,
    Recruit,
    RecruitMark,
    TrainingCourse,
    TrainingIntake,
)

CustomUser = get_user_model()


class TrainingWingTestMixin:
    """Shared fixtures for the training wing tests."""

    @classmethod
    def setUpTestData(cls):
        cls.region, _ = Region.objects.get_or_create(
            code='test-central',
            defaults={'name': 'Test Central Region'},
        )
        cls.station = PrisonStation.objects.create(
            name='Maula Prison',
            region=cls.region,
            location='Lilongwe',
            capacity=800,
            date_established=date(1965, 1, 1),
        )
        cls.training_officer = CustomUser.objects.create_user(
            username='training1',
            password='testpass123',
            role=CustomUser.ROLE_TRAINING_WING_OFFICER,
        )
        cls.station_hr = CustomUser.objects.create_user(
            username='stationhr1',
            password='testpass123',
            role=CustomUser.ROLE_STATION_HR,
            prison_station=cls.station,
            region=cls.region,
        )
        Rank.objects.create(name='warder')

    def create_intake(self, intake_number=1, year=None):
        start = date(year or date.today().year, 1, 10)
        return TrainingIntake.objects.create(
            intake_number=intake_number,
            intake_suffix='st',
            year=start.year,
            start_date=start,
            estimated_end_date=start + timedelta(days=180),
            pass_out_date=start + timedelta(days=200),
            created_by=self.training_officer,
        )

    def create_recruit(self, intake, surname='Banda', **kwargs):
        defaults = {
            'first_name': 'Test',
            'surname': surname,
            'date_of_birth': date(1998, 5, 4),
            'gender': 'male',
            'next_of_kin': 'Jane Banda',
            'next_of_kin_relationship': 'Mother',
            'next_of_kin_contact': '+265991000000',
            'next_of_kin_address': 'Lilongwe',
        }
        defaults.update(kwargs)
        return Recruit.objects.create(intake=intake, **defaults)

    def create_course(self, course_code='prisons_acts', **kwargs):
        defaults = {
            'category': 'security_ops_1',
            'name': 'Malawi Prisons Acts',
            'total_marks': 100,
            'passing_mark': 50,
        }
        defaults.update(kwargs)
        return TrainingCourse.objects.create(course_code=course_code, **defaults)


class TrainingCurriculumCommandTests(TrainingWingTestMixin, TestCase):
    def test_command_creates_every_standard_course(self):
        call_command('populate_training_curriculum')

        self.assertEqual(
            TrainingCourse.objects.count(),
            len(TrainingCourse.COURSE_CHOICES),
        )
        course = TrainingCourse.objects.first()
        self.assertTrue(course.category)
        self.assertEqual(course.total_marks, 100)
        self.assertEqual(course.passing_mark, 50)

    def test_command_is_idempotent(self):
        call_command('populate_training_curriculum')
        call_command('populate_training_curriculum')

        self.assertEqual(
            TrainingCourse.objects.count(),
            len(TrainingCourse.COURSE_CHOICES),
        )


class TrainingModelTests(TrainingWingTestMixin, TestCase):
    def setUp(self):
        self.intake = self.create_intake()
        self.course = TrainingCourse.objects.create(
            course_code='prisons_acts',
            category='security_ops_1',
            name='Malawi Prisons Acts',
            total_marks=100,
            passing_mark=50,
        )

    def test_intake_display_name_uses_suffix(self):
        self.assertIn('1st', self.intake.get_display_name())

    def test_recruit_gets_sequential_training_ids(self):
        first = self.create_recruit(self.intake, surname='One')
        second = self.create_recruit(self.intake, surname='Two')

        self.assertEqual(first.training_id, 'R-001/001')
        self.assertEqual(second.training_id, 'R-001/002')

    def test_training_id_is_not_reused_after_deletion(self):
        first = self.create_recruit(self.intake, surname='One')
        self.create_recruit(self.intake, surname='Two')
        first.delete()

        third = self.create_recruit(self.intake, surname='Three')
        self.assertEqual(third.training_id, 'R-001/003')

    def test_recruit_creation_seeds_marks_for_required_courses(self):
        recruit = self.create_recruit(self.intake)

        self.assertEqual(recruit.marks.count(), 1)
        self.assertEqual(recruit.marks.first().course, self.course)

    def test_marks_update_overall_score_and_grade(self):
        recruit = self.create_recruit(self.intake)
        mark = recruit.marks.get(course=self.course)
        mark.obtained_marks = 80
        mark.save()

        recruit.refresh_from_db()
        self.assertEqual(float(recruit.overall_score), 80.0)
        self.assertTrue(recruit.final_grade)

    def test_ranking_orders_recruits_by_score(self):
        top = self.create_recruit(self.intake, surname='Top')
        bottom = self.create_recruit(self.intake, surname='Bottom')

        top.marks.update(obtained_marks=90)
        top.calculate_final_results()
        bottom.marks.update(obtained_marks=55)
        bottom.calculate_final_results()

        rank, total = top.get_current_ranking()
        self.assertEqual((rank, total), (1, 2))
        self.assertEqual(bottom.get_current_ranking()[0], 2)


class TrainingPermissionTests(TrainingWingTestMixin, TestCase):
    def test_training_dashboard_requires_login(self):
        response = self.client.get(reverse('hrms:training_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_training_wing_officer_can_open_dashboard(self):
        self.client.force_login(self.training_officer)
        response = self.client.get(reverse('hrms:training_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_station_hr_cannot_open_training_dashboard(self):
        self.client.force_login(self.station_hr)
        response = self.client.get(reverse('hrms:training_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_training_officer_lands_on_training_dashboard_after_login(self):
        CustomUser.objects.filter(pk=self.training_officer.pk).update(
            must_change_password=False,
        )
        response = self.client.post(
            reverse('login'),
            {'username': 'training1', 'password': 'testpass123'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain[-1][0],
            reverse('hrms:training_dashboard'),
        )

    def test_login_forces_password_change_before_landing_page(self):
        response = self.client.post(
            reverse('login'),
            {'username': 'training1', 'password': 'testpass123'},
            follow=True,
        )
        self.assertEqual(
            response.redirect_chain[-1][0],
            reverse('change_password'),
        )


class TrainingViewFlowTests(TrainingWingTestMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.training_officer)

    def test_course_create_rejects_passing_mark_above_total(self):
        response = self.client.post(reverse('hrms:course_create'), {
            'course_code': 'prisons_acts',
            'category': 'security_ops_1',
            'name': '',
            'description': '',
            'total_marks': 100,
            'passing_mark': 120,
            'duration_hours': 10,
            'is_required': 'on',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(TrainingCourse.objects.count(), 0)

    def test_course_create_uses_curriculum_name_when_blank(self):
        response = self.client.post(reverse('hrms:course_create'), {
            'course_code': 'prisons_acts',
            'category': 'security_ops_1',
            'name': '',
            'description': '',
            'total_marks': 100,
            'passing_mark': 50,
            'duration_hours': 10,
            'is_required': 'on',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 302)
        course = TrainingCourse.objects.get(course_code='prisons_acts')
        self.assertTrue(course.name)

    def test_intake_create_rejects_pass_out_before_start(self):
        response = self.client.post(reverse('hrms:intake_create'), {
            'intake_number': 5,
            'intake_suffix': 'th',
            'custom_suffix': '',
            'year': 2026,
            'start_date': '2026-03-01',
            'estimated_end_date': '2026-01-01',
            'pass_out_date': '2026-02-01',
            'description': '',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrainingIntake.objects.exists())

    def test_intake_create_requires_custom_suffix_when_selected(self):
        response = self.client.post(reverse('hrms:intake_create'), {
            'intake_number': 6,
            'intake_suffix': 'custom',
            'custom_suffix': '',
            'year': 2026,
            'start_date': '2026-03-01',
            'estimated_end_date': '2026-09-01',
            'pass_out_date': '2026-09-20',
            'description': '',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(TrainingIntake.objects.exists())

    def test_intake_create_succeeds_with_valid_data(self):
        response = self.client.post(reverse('hrms:intake_create'), {
            'intake_number': 7,
            'intake_suffix': 'th',
            'custom_suffix': '',
            'year': 2026,
            'start_date': '2026-03-01',
            'estimated_end_date': '2026-09-01',
            'pass_out_date': '2026-09-20',
            'description': 'Basic training',
            'is_active': 'on',
        })

        self.assertEqual(response.status_code, 302)
        intake = TrainingIntake.objects.get(intake_number=7)
        self.assertEqual(intake.created_by, self.training_officer)

    def test_recruit_create_rejects_underage_recruit(self):
        intake = self.create_intake(intake_number=8)
        response = self.client.post(
            reverse('hrms:recruit_create', kwargs={'intake_pk': intake.pk}),
            {
                'first_name': 'Too',
                'surname': 'Young',
                'date_of_birth': date.today().isoformat(),
                'gender': 'male',
                'recruit_type': 'recruit',
                'next_of_kin': 'Parent',
                'next_of_kin_relationship': 'Father',
                'next_of_kin_contact': '+265991000000',
                'next_of_kin_address': 'Lilongwe',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Recruit.objects.exists())

    def test_recruit_create_and_mark_entry(self):
        intake = self.create_intake(intake_number=9)
        course = self.create_course()

        response = self.client.post(
            reverse('hrms:recruit_create', kwargs={'intake_pk': intake.pk}),
            {
                'first_name': 'Chimwemwe',
                'surname': 'Phiri',
                'date_of_birth': '1998-04-04',
                'gender': 'female',
                'recruit_type': 'recruit',
                'contact_number': '+265991000000',
                'home_district': 'Lilongwe',
                'next_of_kin': 'Parent',
                'next_of_kin_relationship': 'Father',
                'next_of_kin_contact': '+265991000000',
                'next_of_kin_address': 'Lilongwe',
            },
        )
        self.assertEqual(response.status_code, 302)
        recruit = Recruit.objects.get(surname='Phiri')
        self.assertTrue(recruit.training_id)
        self.assertEqual(recruit.marks.count(), 1)

        # Marks above the course total must be rejected.
        response = self.client.post(
            reverse('hrms:add_mark', kwargs={'recruit_pk': recruit.pk}),
            {
                'course': course.pk,
                'obtained_marks': '150',
                'exam_date': date.today().isoformat(),
                'remarks': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(float(recruit.marks.get(course=course).obtained_marks), 0.0)

        response = self.client.post(
            reverse('hrms:add_mark', kwargs={'recruit_pk': recruit.pk}),
            {
                'course': course.pk,
                'obtained_marks': '72.5',
                'exam_date': date.today().isoformat(),
                'remarks': 'Good',
            },
        )
        self.assertEqual(response.status_code, 302)
        recruit.refresh_from_db()
        self.assertEqual(float(recruit.overall_score), 72.5)

    def test_edit_mark_validates_range(self):
        intake = self.create_intake(intake_number=10)
        course = self.create_course()
        recruit = self.create_recruit(intake)
        mark = recruit.marks.get(course=course)

        response = self.client.post(
            reverse('hrms:edit_mark', kwargs={'pk': mark.pk}),
            {
                'obtained_marks': '-5',
                'exam_date': date.today().isoformat(),
                'remarks': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        mark.refresh_from_db()
        self.assertEqual(float(mark.obtained_marks), 0.0)

        response = self.client.post(
            reverse('hrms:edit_mark', kwargs={'pk': mark.pk}),
            {
                'obtained_marks': '61',
                'exam_date': date.today().isoformat(),
                'remarks': 'Resit',
            },
        )
        self.assertEqual(response.status_code, 302)
        mark.refresh_from_db()
        self.assertEqual(float(mark.obtained_marks), 61.0)

    def test_training_pages_render(self):
        intake = self.create_intake(intake_number=11)
        self.create_course()
        recruit = self.create_recruit(intake)
        mark = recruit.marks.first()

        urls = [
            reverse('hrms:training_dashboard'),
            reverse('hrms:intake_list'),
            reverse('hrms:intake_create'),
            reverse('hrms:intake_detail', kwargs={'pk': intake.pk}),
            reverse('hrms:intake_graduation', kwargs={'pk': intake.pk}),
            reverse('hrms:class_ranking', kwargs={'pk': intake.pk}),
            reverse('hrms:course_list'),
            reverse('hrms:course_create'),
            reverse('hrms:recruit_list'),
            reverse('hrms:recruit_create', kwargs={'intake_pk': intake.pk}),
            reverse('hrms:recruit_detail', kwargs={'pk': recruit.pk}),
            reverse('hrms:recruit_update', kwargs={'pk': recruit.pk}),
            reverse('hrms:add_mark', kwargs={'recruit_pk': recruit.pk}),
            reverse('hrms:edit_mark', kwargs={'pk': mark.pk}),
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


class GraduationFlowTests(TrainingWingTestMixin, TestCase):
    def setUp(self):
        self.client.force_login(self.training_officer)
        self.intake = self.create_intake(intake_number=12)
        self.course = self.create_course()
        self.top = self.create_recruit(self.intake, surname='Top')
        self.bottom = self.create_recruit(self.intake, surname='Bottom')
        for recruit, score in ((self.top, 88), (self.bottom, 40)):
            mark = recruit.marks.get(course=self.course)
            mark.obtained_marks = score
            mark.save()

    def test_graduation_requires_ceremony_details(self):
        response = self.client.post(
            reverse('hrms:intake_graduation', kwargs={'pk': self.intake.pk}),
            {'graduation_date': '', 'ceremony_location': ''},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(GraduationBatch.objects.exists())
        self.assertEqual(Recruit.objects.filter(status='graduated').count(), 0)

    def test_graduation_assigns_service_numbers_and_creates_officers(self):
        graduation_date = date.today().isoformat()
        response = self.client.post(
            reverse('hrms:intake_graduation', kwargs={'pk': self.intake.pk}),
            {
                'graduation_date': graduation_date,
                'ceremony_location': 'Mikuyu Training School',
            },
        )
        self.assertEqual(response.status_code, 302)

        self.top.refresh_from_db()
        self.bottom.refresh_from_db()

        self.assertEqual(self.top.status, 'graduated')
        self.assertEqual(self.top.rank_in_class, 1)
        self.assertEqual(self.bottom.rank_in_class, 2)
        self.assertEqual(
            int(self.top.service_number),
            Recruit.DEFAULT_SERVICE_NUMBER_START,
        )
        self.assertEqual(
            int(self.bottom.service_number),
            Recruit.DEFAULT_SERVICE_NUMBER_START + 1,
        )

        batch = GraduationBatch.objects.get(intake=self.intake)
        self.assertEqual(batch.total_graduates, 2)
        self.assertEqual(batch.total_passed, 1)
        self.assertEqual(batch.total_failed, 1)
        self.assertEqual(batch.best_performing_recruit, self.top)

        self.assertEqual(Officer.objects.count(), 2)
        officer = Officer.objects.get(service_number=self.top.service_number)
        self.assertEqual(officer.surname, 'Top')
        self.assertEqual(officer.status, 'active')
        self.assertEqual(officer.date_joined_service.isoformat(), graduation_date)

        self.intake.refresh_from_db()
        self.assertFalse(self.intake.is_active)

    def test_graduation_rejected_when_no_recruits_are_eligible(self):
        Recruit.objects.filter(intake=self.intake).update(status='withdrawn')

        response = self.client.post(
            reverse('hrms:intake_graduation', kwargs={'pk': self.intake.pk}),
            {
                'graduation_date': date.today().isoformat(),
                'ceremony_location': 'Mikuyu Training School',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(GraduationBatch.objects.exists())
        self.assertFalse(RecruitMark.objects.filter(recruit__status='graduated').exists())
