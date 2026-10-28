from django.contrib import admin
from .models import Movie, Screening, Reservation, Rating, Comment


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "year", "duration")
    search_fields = ("title",)


@admin.register(Screening)
class ScreeningAdmin(admin.ModelAdmin):
    list_display = ("movie", "starts_at", "hall", "seat_rows", "seat_cols")
    list_filter = ("movie", "hall")
    date_hierarchy = "starts_at"


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("user", "screening", "seat_row", "seat_col", "created_at")
    list_filter = ("user", "screening__movie")
    search_fields = ("user__username",)


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "stars")
    list_filter = ("movie", "stars")
    search_fields = ("user__username", "movie__title")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "movie", "short_body", "created_at")
    list_filter = ("movie", "user")
    search_fields = ("user__username", "movie__title", "body")

    @admin.display(description="Treść")
    def short_body(self, obj):
        return obj.body[:60]
