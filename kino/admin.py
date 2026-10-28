from django.contrib import admin
from .models import Movie, Screening, Reservation, Rating, Comment

admin.site.register(Movie)
admin.site.register(Screening)
admin.site.register(Reservation)
admin.site.register(Rating)
admin.site.register(Comment)

