from rest_framework import mixins, permissions, viewsets
from rest_framework.generics import CreateAPIView
from drf_spectacular.utils import OpenApiExample, extend_schema, extend_schema_view

from .models import Booking, Category, Review, Tour
from .serializers import (
    BookingSerializer,
    CategorySerializer,
    RegistrationSerializer,
    ReviewSerializer,
    TourSerializer,
)


@extend_schema_view(
    post=extend_schema(
        summary="Зарегистрировать участника",
        description=(
            "Создаёт учётную запись и связанный профиль 1:1. Пароль не возвращается "
            "в ответе; телефон необязателен."
        ),
        examples=[
            OpenApiExample(
                "Регистрация участника",
                value={
                    "username": "rider",
                    "email": "rider@example.com",
                    "password": "secure-pass-123",
                    "phone": "+79990000000",
                },
                request_only=True,
            )
        ],
    )
)
class RegistrationView(CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [permissions.AllowAny]


class AdminWriteReadOnlyViewSet(viewsets.ModelViewSet):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


@extend_schema_view(
    list=extend_schema(summary="Получить список категорий"),
    retrieve=extend_schema(summary="Получить категорию"),
    create=extend_schema(
        summary="Создать категорию",
        description="Требуется авторизация администратора. Название и slug должны быть уникальными.",
        examples=[
            OpenApiExample(
                "Категория конного тура",
                value={"name": "Конный", "slug": "horseback"},
                request_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Полностью обновить категорию",
        description="Требуется авторизация администратора; передайте name и slug.",
        examples=[
            OpenApiExample(
                "Обновление категории",
                value={"name": "Конный тур", "slug": "horseback-tour"},
                request_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Частично обновить категорию",
        description="Требуется авторизация администратора; передайте изменяемые поля.",
        examples=[
            OpenApiExample(
                "Изменение названия",
                value={"name": "Конные прогулки"},
                request_only=True,
            )
        ],
    ),
    destroy=extend_schema(summary="Удалить категорию (администратор)"),
)
class CategoryViewSet(AdminWriteReadOnlyViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


@extend_schema_view(
    list=extend_schema(summary="Получить список опубликованных туров"),
    retrieve=extend_schema(summary="Получить тур"),
    create=extend_schema(
        summary="Создать тур",
        description=(
            "Требуется авторизация администратора. Передайте категории как список "
            "существующих ID; цена должна быть неотрицательной, длительность — больше нуля."
        ),
        examples=[
            OpenApiExample(
                "Конная прогулка",
                value={
                    "title": "Конная прогулка по лесу",
                    "description": "Маршрут для начинающих",
                    "price": "2500.00",
                    "duration_minutes": 120,
                    "categories": [1],
                    "is_active": True,
                },
                request_only=True,
            )
        ],
    ),
    update=extend_schema(
        summary="Полностью обновить тур",
        description="Требуется авторизация администратора; передайте все поля тура.",
        examples=[
            OpenApiExample(
                "Обновление тура",
                value={
                    "title": "Конная прогулка по лесу",
                    "description": "Обновлённое описание маршрута",
                    "price": "2700.00",
                    "duration_minutes": 150,
                    "categories": [1, 2],
                    "is_active": True,
                },
                request_only=True,
            )
        ],
    ),
    partial_update=extend_schema(
        summary="Частично обновить тур",
        description="Требуется авторизация администратора; передайте изменяемые поля.",
        examples=[
            OpenApiExample(
                "Изменение цены",
                value={"price": "2700.00"},
                request_only=True,
            )
        ],
    ),
    destroy=extend_schema(summary="Удалить тур (администратор)"),
)
class TourViewSet(AdminWriteReadOnlyViewSet):
    serializer_class = TourSerializer

    def get_queryset(self):
        queryset = Tour.objects.prefetch_related("categories")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(is_active=True)


@extend_schema_view(
    list=extend_schema(summary="Получить свои бронирования"),
    retrieve=extend_schema(summary="Получить своё бронирование"),
    create=extend_schema(
        summary="Забронировать тур",
        description=(
            "Требуется авторизация. Поля user и status задаются сервисом. Участник "
            "может иметь только одно активное бронирование на точное время начала "
            "независимо от тура. Для повторной записи отмените предыдущее бронирование."
        ),
        examples=[
            OpenApiExample(
                "Бронирование тура",
                value={"tour": 1, "scheduled_at": "2027-06-15T10:00:00+03:00"},
                request_only=True,
            )
        ],
    ),
)
class BookingViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        queryset = Booking.objects.select_related("tour", "user")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)


@extend_schema_view(
    list=extend_schema(summary="Получить свои отзывы"),
    create=extend_schema(
        summary="Оставить отзыв о завершённом туре",
        description=(
            "Требуется авторизация. Отзыв можно оставить только о собственном "
            "завершённом бронировании. Допускается несколько отзывов на одно бронирование."
        ),
        examples=[
            OpenApiExample(
                "Отзыв",
                value={
                    "booking": 1,
                    "rating": 5,
                    "comment": "Отличный маршрут и спокойные лошади!",
                },
                request_only=True,
            )
        ],
    ),
)
class ReviewViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(booking__user=self.request.user).select_related(
            "booking__user",
            "booking__tour",
        )
