from django.contrib import admin
from django.utils import timezone
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
    # Kolumny: user | seat_row | seat_col | film | data
    list_display = ("user", "seat_row", "seat_col", "movie", "screening_date")
    list_select_related = ("user", "screening__movie")  # jedno zapytanie zamiast N+1
    list_filter = ("screening__movie", ("screening__starts_at", admin.DateFieldListFilter))
    search_fields = ("user__username", "screening__movie__title")
    ordering = ("-screening__starts_at", "seat_row", "seat_col")

    @admin.display(description="Film", ordering="screening__movie__title")
    def movie(self, obj):
        return obj.screening.movie.title

    @admin.display(description="Data seansu", ordering="screening__starts_at")
    def screening_date(self, obj):
        return timezone.localtime(obj.screening.starts_at).strftime("%d.%m.%Y %H:%M")


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
