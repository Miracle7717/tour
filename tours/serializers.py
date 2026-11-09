from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers

from .models import Booking, Category, Review, Tour, UserProfile


User = get_user_model()


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        help_text="Пароль длиной не менее 8 символов.",
    )
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=32,
        help_text="Необязательный номер телефона.",
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "phone"]
        read_only_fields = ["id"]

    @transaction.atomic
    def create(self, validated_data):
        phone = validated_data.pop("phone", "")
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        UserProfile.objects.create(user=user, phone=phone)
        return user


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "name": {"help_text": "Название категории, например «Конный»."},
            "slug": {"help_text": "Уникальный URL-код категории."},
        }


class TourSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        help_text="Список ID категорий тура, например [1, 2].",
    )
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0,
        help_text="Цена тура, неотрицательное число с двумя знаками после запятой.",
    )
    duration_minutes = serializers.IntegerField(
        min_value=1,
        help_text="Продолжительность тура в минутах.",
    )

    class Meta:
        model = Tour
        fields = [
            "id",
            "title",
            "description",
            "price",
            "duration_minutes",
            "categories",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class BookingSerializer(serializers.ModelSerializer):
    tour = serializers.PrimaryKeyRelatedField(
        queryset=Tour.objects.all(),
        help_text="ID опубликованного тура.",
    )
    scheduled_at = serializers.DateTimeField(
        help_text="Дата и время начала тура в формате ISO 8601 с часовым поясом.",
    )
    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
        help_text="Устанавливается автоматически по авторизованному пользователю.",
    )
    status = serializers.ChoiceField(
        choices=Booking.Status.choices,
        read_only=True,
        help_text="Устанавливается сервисом; новый заказ получает статус pending.",
    )

    class Meta:
        model = Booking
        fields = ["id", "user", "tour", "scheduled_at", "status", "created_at"]
        read_only_fields = ["id", "user", "status", "created_at"]

    def validate_tour(self, tour):
        if not tour.is_active:
            raise serializers.ValidationError("Нельзя забронировать снятый с публикации тур.")
        return tour

    def validate(self, attrs):
        user = self.context["request"].user
        scheduled_at = attrs.get("scheduled_at")
        if scheduled_at and Booking.objects.filter(
            user=user,
            scheduled_at=scheduled_at,
        ).exclude(status=Booking.Status.CANCELLED).exists():
            raise serializers.ValidationError(
                {"scheduled_at": "У вас уже есть бронирование на эту дату и время."}
            )
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        try:
            with transaction.atomic():
                return super().create(validated_data)
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"scheduled_at": "У вас уже есть бронирование на эту дату и время."}
            ) from exc


class ReviewSerializer(serializers.ModelSerializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.none(),
        help_text="ID собственного завершённого бронирования.",
    )
    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
        help_text="Оценка завершённого тура от 1 до 5.",
    )
    comment = serializers.CharField(
        help_text="Текст отзыва; пустой комментарий не допускается.",
    )
    user = serializers.ReadOnlyField(source="booking.user.username")
    tour = serializers.ReadOnlyField(source="booking.tour.title")

    class Meta:
        model = Review
        fields = ["id", "booking", "user", "tour", "rating", "comment", "created_at"]
        read_only_fields = ["id", "user", "tour", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["booking"].queryset = Booking.objects.filter(
                user=request.user,
                status=Booking.Status.COMPLETED,
            ).select_related("user", "tour")

    def validate_rating(self, rating):
        if not 1 <= rating <= 5:
            raise serializers.ValidationError("Оценка должна быть от 1 до 5.")
        return rating

    def validate_comment(self, comment):
        if not comment.strip():
            raise serializers.ValidationError("Комментарий не может быть пустым.")
        return comment
