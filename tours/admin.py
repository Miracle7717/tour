from django.contrib import admin

from .models import Booking, Category, Review, Tour, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "phone", "created_at"]
    search_fields = ["user__username", "user__email", "phone"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Tour)
class TourAdmin(admin.ModelAdmin):
    list_display = ["title", "price", "duration_minutes", "is_active"]
    list_filter = ["is_active", "categories"]
    search_fields = ["title", "description"]
    filter_horizontal = ["categories"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["user", "tour", "scheduled_at", "status"]
    list_filter = ["status", "scheduled_at"]
    search_fields = ["user__username", "tour__title"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["booking", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
