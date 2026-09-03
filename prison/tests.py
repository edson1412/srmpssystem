from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from prison.models import ConvictedPrisoner, Prisoner, PrisonerReleaseReview, PrisonStation


class ReleaseHubTests(TestCase):
    def setUp(self):
        self.station = PrisonStation.objects.create(
            name='Main Station',
            code='MAIN',
            location='Blantyre',
            region='southern',
            capacity=100,
            date_established=timezone.now().date(),
            created_by=None,
        )
        self.reception_user = get_user_model().objects.create_user(
            username='reception',
            password='secret123',
            role='reception',
            rank='warder',
            prison_station=self.station,
        )
        self.officer_user = get_user_model().objects.create_user(
            username='officer',
            password='secret123',
            role='officer_in_charge',
            rank='sergeant',
            prison_station=self.station,
        )
        self.station_user = get_user_model().objects.create_user(
            username='station',
            password='secret123',
            role='station_officer',
            rank='gaoler',
            prison_station=self.station,
        )
        self.prisoner = Prisoner.objects.create(
            prisoner_number='P-1001',
            first_name='John',
            surname='Doe',
            sex='male',
            age=34,
            prisoner_class='convicted',
            prison_station=self.station,
            block_number='A',
            cell_number='1',
            date_admitted=timezone.now().date(),
            created_by=self.reception_user,
        )
        self.convicted = ConvictedPrisoner.objects.create(
            prisoner=self.prisoner,
            sentence=0.1,
            court='High Court',
            date_of_committal=timezone.now().date() - timedelta(days=60),
            wef_date=timezone.now().date() + timedelta(days=1),
            reduction_months=0,
        )

    def test_reception_hub_lists_prisoners_due_for_release_within_five_days(self):
        self.client.force_login(self.reception_user)
        response = self.client.get(reverse('release_hub'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        self.assertContains(response, 'Forward for review')

    def test_forwarding_for_review_creates_pending_review_and_officer_hub_lists_it(self):
        self.client.force_login(self.reception_user)
        response = self.client.post(
            reverse('forward_release_for_review', args=[self.prisoner.pk]),
            {'review_role': 'officer_in_charge'},
        )

        self.assertEqual(response.status_code, 302)
        review = PrisonerReleaseReview.objects.get(prisoner=self.prisoner, review_role='officer_in_charge')
        self.assertEqual(review.status, 'pending')

        self.client.force_login(self.officer_user)
        officer_response = self.client.get(reverse('release_hub'))
        self.assertContains(officer_response, 'John Doe')

    def test_approval_releases_the_prisoner(self):
        review = PrisonerReleaseReview.objects.create(
            prisoner=self.prisoner,
            requested_by=self.reception_user,
            review_role='station_officer',
            station=self.station,
            release_date=timezone.now().date() + timedelta(days=2),
            status='pending',
        )

        self.client.force_login(self.station_user)
        response = self.client.post(reverse('approve_release_review', args=[review.pk]))

        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        self.prisoner.refresh_from_db()
        self.assertEqual(review.status, 'approved')
        self.assertFalse(self.prisoner.is_active)
        self.assertEqual(self.prisoner.date_released, timezone.now().date())
