from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Booking, Category, Review, Tour, UserProfile


User = get_user_model()


class TourApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="rider", password="secure-pass-123")
        self.other_user = User.objects.create_user(username="other", password="secure-pass-123")
        self.staff = User.objects.create_superuser(
            username="manager",
            email="manager@example.com",
            password="secure-pass-123",
        )
        self.category = Category.objects.create(name="Конный", slug="horseback")
        self.second_category = Category.objects.create(name="Пеший", slug="walking")
        self.tour = Tour.objects.create(
            title="Лесная прогулка",
            description="Маршрут по лесу",
            price=Decimal("2500.00"),
            duration_minutes=120,
        )
        self.tour.categories.add(self.category)

    def test_registration_creates_user_and_one_to_one_profile(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "new-rider",
                "email": "new@example.com",
                "password": "valid-pass-987",
                "phone": "+79990000000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(username="new-rider")
        self.assertTrue(created_user.check_password("valid-pass-987"))
        self.assertEqual(created_user.profile.phone, "+79990000000")
        self.assertEqual(UserProfile.objects.filter(user=created_user).count(), 1)
        self.assertNotIn("password", response.data)

    def test_registration_rejects_invalid_or_duplicate_data(self):
        short_password = self.client.post(
            reverse("register"),
            {"username": "short", "password": "123"},
            format="json",
        )
        duplicate_username = self.client.post(
            reverse("register"),
            {"username": "rider", "password": "valid-pass-987"},
            format="json",
        )
        self.assertEqual(short_password.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_username.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_and_tour_creation_requires_admin_and_saves_many_to_many(self):
        category_response = self.client.post(
            reverse("category-list"),
            {"name": "Мото", "slug": "moto"},
            format="json",
        )
        self.assertEqual(category_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.staff)
        category_response = self.client.post(
            reverse("category-list"),
            {"name": "Мото", "slug": "moto"},
            format="json",
        )
        self.assertEqual(category_response.status_code, status.HTTP_201_CREATED)
        moto_category_id = category_response.data["id"]

        tour_response = self.client.post(
            reverse("tour-list"),
            {
                "title": "Смешанный маршрут",
                "description": "Конная и пешая часть",
                "price": "3000.00",
                "duration_minutes": 180,
                "categories": [self.category.id, self.second_category.id, moto_category_id],
            },
            format="json",
        )
        self.assertEqual(tour_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(tour_response.data["categories"]), 3)
        self.assertEqual(Tour.objects.get(pk=tour_response.data["id"]).categories.count(), 3)

    def test_category_and_tour_creation_reject_invalid_data(self):
        self.client.force_authenticate(self.staff)
        bad_category = self.client.post(
            reverse("category-list"),
            {"name": "Конный", "slug": "horseback"},
            format="json",
        )
        duplicate_slug = self.client.post(
            reverse("category-list"),
            {"name": "Конная прогулка", "slug": "horseback"},
            format="json",
        )
        bad_tour = self.client.post(
            reverse("tour-list"),
            {
                "title": "",
                "description": "",
                "price": "-10",
                "duration_minutes": 0,
                "categories": [99999],
            },
            format="json",
        )
        self.assertEqual(bad_category.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(duplicate_slug.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(bad_tour.status_code, status.HTTP_400_BAD_REQUEST)

    def test_category_and_tour_update_and_delete_requests(self):
        self.client.force_authenticate(self.staff)

        category_url = reverse("category-detail", args=[self.second_category.id])
        category_put = self.client.put(
            category_url,
            {"name": "Пеший тур", "slug": "walking-tour"},
            format="json",
        )
        category_patch = self.client.patch(
            category_url,
            {"name": "Пешеходный"},
            format="json",
        )
        self.assertEqual(category_put.status_code, status.HTTP_200_OK)
        self.assertEqual(category_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(category_patch.data["name"], "Пешеходный")

        tour_url = reverse("tour-detail", args=[self.tour.id])
        tour_put = self.client.put(
            tour_url,
            {
                "title": "Лесной маршрут",
                "description": "Полное обновление",
                "price": "2600.00",
                "duration_minutes": 150,
                "categories": [self.category.id, self.second_category.id],
                "is_active": True,
            },
            format="json",
        )
        tour_patch = self.client.patch(
            tour_url,
            {"price": "2750.00"},
            format="json",
        )
        self.assertEqual(tour_put.status_code, status.HTTP_200_OK)
        self.assertEqual(tour_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(tour_patch.data["price"], "2750.00")
        self.assertEqual(Tour.objects.get(pk=self.tour.id).categories.count(), 2)

        tour_delete = self.client.delete(tour_url)
        self.assertEqual(tour_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tour.objects.filter(pk=self.tour.id).exists())

        category_delete = self.client.delete(category_url)
        self.assertEqual(category_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(pk=self.second_category.id).exists())

    def test_public_tour_and_category_lists(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(reverse("tour-list")).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(reverse("category-list")).status_code,
            status.HTTP_200_OK,
        )

    def test_booking_requires_authentication_and_valid_active_tour(self):
        url = reverse("booking-list")
        payload = {
            "tour": self.tour.id,
            "scheduled_at": (timezone.now() + timedelta(days=3)).isoformat(),
        }
        anonymous_response = self.client.post(url, payload, format="json")
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

        inactive_tour = Tour.objects.create(
            title="Закрытый тур",
            description="Недоступен",
            price=Decimal("1000.00"),
            duration_minutes=60,
            is_active=False,
        )
        self.client.force_authenticate(self.user)
        invalid_response = self.client.post(
            url,
            {"tour": inactive_tour.id, "scheduled_at": payload["scheduled_at"]},
            format="json",
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_rejects_missing_or_invalid_submission_fields(self):
        self.client.force_authenticate(self.user)
        url = reverse("booking-list")
        missing_time = self.client.post(
            url,
            {"tour": self.tour.id},
            format="json",
        )
        unknown_tour = self.client.post(
            url,
            {
                "tour": 99999,
                "scheduled_at": (timezone.now() + timedelta(days=2)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(missing_time.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("scheduled_at", missing_time.data)
        self.assertEqual(unknown_tour.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("tour", unknown_tour.data)
        self.assertEqual(Booking.objects.count(), 0)

    def test_user_cannot_book_two_tours_at_same_time_but_can_book_another_time(self):
        self.client.force_authenticate(self.user)
        start = (timezone.now() + timedelta(days=4)).replace(microsecond=0)
        first_response = self.client.post(
            reverse("booking-list"),
            {"tour": self.tour.id, "scheduled_at": start.isoformat()},
            format="json",
        )
        another_tour = Tour.objects.create(
            title="Горная прогулка",
            description="Маршрут в горах",
            price=Decimal("4000.00"),
            duration_minutes=240,
        )
        conflict_response = self.client.post(
            reverse("booking-list"),
            {"tour": another_tour.id, "scheduled_at": start.isoformat()},
            format="json",
        )
        different_time_response = self.client.post(
            reverse("booking-list"),
            {
                "tour": another_tour.id,
                "scheduled_at": (start + timedelta(hours=2)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(conflict_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(different_time_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Booking.objects.filter(user=self.user).count(), 2)

    def test_booking_database_constraint_prevents_duplicate_active_slots(self):
        scheduled_at = timezone.now() + timedelta(days=2)
        Booking.objects.create(user=self.user, tour=self.tour, scheduled_at=scheduled_at)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(
                user=self.user,
                tour=self.tour,
                scheduled_at=scheduled_at,
            )

    def test_cancelled_booking_does_not_block_rebooking_same_slot(self):
        scheduled_at = timezone.now() + timedelta(days=5)
        Booking.objects.create(
            user=self.user,
            tour=self.tour,
            scheduled_at=scheduled_at,
            status=Booking.Status.CANCELLED,
        )
        self.client.force_authenticate(self.user)
        response = self.client.post(
            reverse("booking-list"),
            {"tour": self.tour.id, "scheduled_at": scheduled_at.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_booking_list_is_private_to_each_user(self):
        Booking.objects.create(
            user=self.other_user,
            tour=self.tour,
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        self.client.force_authenticate(self.user)
        response = self.client.get(reverse("booking-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_review_is_allowed_only_for_own_completed_booking_and_can_repeat(self):
        booking = Booking.objects.create(
            user=self.user,
            tour=self.tour,
            scheduled_at=timezone.now() - timedelta(days=1),
            status=Booking.Status.COMPLETED,
        )
        pending_booking = Booking.objects.create(
            user=self.user,
            tour=self.tour,
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        url = reverse("review-list")
        payload = {"booking": booking.id, "rating": 5, "comment": "Отличный маршрут!"}
        anonymous_response = self.client.post(url, payload, format="json")
        self.assertEqual(anonymous_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.force_authenticate(self.user)
        first_response = self.client.post(url, payload, format="json")
        second_response = self.client.post(
            url,
            {"booking": booking.id, "rating": 4, "comment": "Хочу повторить."},
            format="json",
        )
        pending_response = self.client.post(
            url,
            {"booking": pending_booking.id, "rating": 5, "comment": "Ещё не ездил"},
            format="json",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(pending_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.filter(booking=booking).count(), 2)

    def test_review_rejects_invalid_rating_empty_comment_and_another_users_booking(self):
        own_booking = Booking.objects.create(
            user=self.user,
            tour=self.tour,
            scheduled_at=timezone.now() - timedelta(days=2),
            status=Booking.Status.COMPLETED,
        )
        other_booking = Booking.objects.create(
            user=self.other_user,
            tour=self.tour,
            scheduled_at=timezone.now() - timedelta(days=3),
            status=Booking.Status.COMPLETED,
        )
        self.client.force_authenticate(self.user)
        url = reverse("review-list")
        bad_rating = self.client.post(
            url,
            {"booking": own_booking.id, "rating": 6, "comment": "Слишком высокая оценка"},
            format="json",
        )
        empty_comment = self.client.post(
            url,
            {"booking": own_booking.id, "rating": 4, "comment": "  "},
            format="json",
        )
        other_user_booking = self.client.post(
            url,
            {"booking": other_booking.id, "rating": 4, "comment": "Не мой тур"},
            format="json",
        )
        self.assertEqual(bad_rating.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(empty_comment.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(other_user_booking.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 0)

    def test_api_documentation_endpoints_are_available(self):
        schema_response = self.client.get("/api/schema/")
        docs_response = self.client.get("/api/docs/")
        self.assertEqual(schema_response.status_code, status.HTTP_200_OK)
        self.assertIn("/api/auth/register/", schema_response.data["paths"])
        write_operations = [
            ("/api/auth/register/", "post"),
            ("/api/categories/", "post"),
            ("/api/categories/{id}/", "put"),
            ("/api/categories/{id}/", "patch"),
            ("/api/tours/", "post"),
            ("/api/tours/{id}/", "put"),
            ("/api/tours/{id}/", "patch"),
            ("/api/bookings/", "post"),
            ("/api/reviews/", "post"),
        ]
        for path, method in write_operations:
            with self.subTest(path=path, method=method):
                operation = schema_response.data["paths"][path][method]
                self.assertIn("requestBody", operation)
                self.assertTrue(
                    operation["requestBody"]["content"]["application/json"].get("examples")
                )
        self.assertEqual(docs_response.status_code, status.HTTP_200_OK)
