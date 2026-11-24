from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from auditlog.registry import auditlog
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger("kino")

class Movie(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    year = models.IntegerField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.title

class Screening(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='screenings')
    starts_at = models.DateTimeField()
    hall = models.CharField(max_length=100)
    seat_rows = models.IntegerField(default=6)
    seat_cols = models.IntegerField(default=8)

    def __str__(self):
        when = timezone.localtime(self.starts_at).strftime("%d.%m.%Y %H:%M")
        return f"{self.movie.title} - {when} ({self.hall})"

class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    screening = models.ForeignKey(Screening, on_delete=models.CASCADE)
    seat_row = models.IntegerField()
    seat_col = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('screening', 'seat_row', 'seat_col')

class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='ratings')
    stars = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])

    class Meta:
        unique_together = ('user', 'movie')

class Comment(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to='comments/', null=True, blank=True)


auditlog.register(Comment)
auditlog.register(Reservation)


@receiver(post_delete, sender=Comment)
def delete_comment_image(sender, instance, **kwargs):
    """Po usunięciu komentarza kasujemy też plik z Blob Storage (inaczej zostają osierocone pliki)."""
    if instance.image:
        try:
            instance.image.delete(save=False)
        except Exception:
            logger.exception("could not delete image %s from storage", instance.image.name)
