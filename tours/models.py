from django.conf import settings
from django.db import models
from django.db.models import Q


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    phone = models.CharField("Телефон", max_length=32, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    def __str__(self):
        return f"Профиль {self.user.username}"


class Category(models.Model):
    name = models.CharField("Название", max_length=80, unique=True)
    slug = models.SlugField("URL-код", max_length=90, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name


class Tour(models.Model):
    title = models.CharField("Название", max_length=160)
    description = models.TextField("Описание")
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField("Длительность, минут")
    categories = models.ManyToManyField(
        Category,
        related_name="tours",
        verbose_name="Категории",
    )
    is_active = models.BooleanField("Опубликован", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "тур"
        verbose_name_plural = "туры"

    def __str__(self):
        return self.title


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждена"
        COMPLETED = "completed", "Завершена"
        CANCELLED = "cancelled", "Отменена"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings",
        verbose_name="Участник",
    )
    tour = models.ForeignKey(
        Tour,
        on_delete=models.PROTECT,
        related_name="bookings",
        verbose_name="Тур",
    )
    scheduled_at = models.DateTimeField("Дата и время начала")
    status = models.CharField(
        "Статус",
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "scheduled_at"],
                condition=~Q(status="cancelled"),
                name="unique_active_booking_per_user_time",
            )
        ]
        verbose_name = "бронирование"
        verbose_name_plural = "бронирования"

    def __str__(self):
        return f"{self.user.username}: {self.tour.title} ({self.scheduled_at:%d.%m.%Y %H:%M})"


class Review(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Бронирование",
    )
    rating = models.PositiveSmallIntegerField("Оценка")
    comment = models.TextField("Комментарий")
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"

    def __str__(self):
        return f"Отзыв {self.booking.user.username} о туре «{self.booking.tour.title}»"
