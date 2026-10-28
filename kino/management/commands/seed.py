import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from kino.models import Movie, Screening, Reservation, Rating, Comment

MOVIES = [
    ("Incepcja", 2010, 148, "Złodziej wykradający sekrety z ludzkich snów dostaje zadanie wszczepienia myśli do umysłu biznesmena."),
    ("Matrix", 1999, 136, "Haker odkrywa, że świat, który zna, jest symulacją, i dołącza do buntu przeciw maszynom."),
    ("Pulp Fiction", 1994, 154, "Splecione historie gangsterów, boksera i żony szefa mafii w Los Angeles."),
    ("Skazani na Shawshank", 1994, 142, "Niesłusznie skazany bankier przez dekady szuka nadziei w więziennych murach."),
    ("Interstellar", 2014, 169, "Ekipa astronautów rusza przez tunel czasoprzestrzenny, by znaleźć nowy dom dla ludzkości."),
    ("Ojciec chrzestny", 1972, 175, "Saga rodziny Corleone i przejmowania władzy w mafijnym imperium."),
    ("Forrest Gump", 1994, 142, "Prosty chłopak z Alabamy mimowolnie uczestniczy w najważniejszych wydarzeniach Ameryki."),
    ("Gladiator", 2000, 155, "Zdradzony rzymski generał zostaje gladiatorem i dąży do zemsty na cesarzu."),
]

# (nazwa sali, liczba rzędów, liczba kolumn)
HALLS = [("Sala 1", 6, 8), ("Sala 2", 8, 10), ("Sala 3", 5, 6)]
HOURS = [(16, 0), (19, 0), (21, 30)]


class Command(BaseCommand):
    help = "Wypełnia bazę przykładowymi filmami, seansami, ocenami i komentarzami."

    def handle(self, *args, **options):
        # Filmy
        movies = []
        for title, year, duration, desc in MOVIES:
            m, _ = Movie.objects.get_or_create(
                title=title,
                defaults={"year": year, "duration": duration, "description": desc},
            )
            movies.append(m)

        # Seanse:
        base = timezone.now().replace(second=0, microsecond=0)
        created = 0
        for i, m in enumerate(movies):
            if m.screenings.exists():
                continue
            for d in range(1, 7):
                if (d + i) % 2:          
                    h, mi = HOURS[(d + i) % len(HOURS)]
                    starts = (base + timedelta(days=d)).replace(hour=h, minute=mi)
                    hall, rows, cols = HALLS[(d + i) % len(HALLS)]
                    Screening.objects.create(
                        movie=m, starts_at=starts, hall=hall,
                        seat_rows=rows, seat_cols=cols,
                    )
                    created += 1

        # Użytkownicy demo, oceny, komentarze
        users = []
        for name in ("demo1", "demo2", "demo3"):
            u, new = User.objects.get_or_create(username=name)
            if new:
                u.set_password("demo1234")
                u.save()
            users.append(u)

        for i, m in enumerate(movies):
            for j, u in enumerate(users):
                Rating.objects.get_or_create(
                    user=u, movie=m, defaults={"stars": 6 + (i + j) % 5}
                )
                
        # Zajęte miejsca na części seansów (unique_together chroni przed dublami)
        rng = random.Random(42)
        reserved = 0
        for sc in Screening.objects.filter(starts_at__gt=timezone.now()):
            if sc.reservation_set.exists():
                continue
            for _ in range(rng.randint(3, 10)):
                _, new = Reservation.objects.get_or_create(
                    screening=sc,
                    seat_row=rng.randint(1, sc.seat_rows),
                    seat_col=rng.randint(1, sc.seat_cols),
                    defaults={"user": rng.choice(users)},
                )
                reserved += new

        first = movies[0]
        if not first.comments.exists():
            Comment.objects.create(movie=first, user=users[0], body="Świetny film, warto zobaczyć na dużym ekranie!")
            Comment.objects.create(movie=first, user=users[1], body="Zakończenie nadal daje do myślenia.")

        self.stdout.write(self.style.SUCCESS(
            f"Gotowe: filmów {Movie.objects.count()}, nowych seansów {created}, zajętych miejsc {reserved}, "
            f"użytkowników demo: demo1/demo2/demo3 (hasło: demo1234)."
        ))