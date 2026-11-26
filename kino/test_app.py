from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from kino.models import Comment, Movie, Rating, Reservation, Screening

# Do test: media i static zapisywane lokalnie
TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD = "Test-pass-12345!"


@override_settings(STORAGES=TEST_STORAGES)
class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.movie = Movie.objects.create(title="Matrix", description="Opis", year=1999, duration=136)
        cls.screening = Screening.objects.create(
            movie=cls.movie,
            starts_at=timezone.now() + timedelta(days=2),
            hall="Sala 1",
            seat_rows=5,
            seat_cols=5,
        )
        cls.past_screening = Screening.objects.create(
            movie=cls.movie,
            starts_at=timezone.now() - timedelta(days=1),
            hall="Sala 2",
            seat_rows=5,
            seat_cols=5,
        )
        cls.anna = User.objects.create_user("anna", "anna@example.com", PASSWORD)
        cls.bob = User.objects.create_user("bob", "bob@example.com", PASSWORD)

    def login(self, user):
        self.client.force_login(user)


class PagesTests(BaseTest):
    def test_strona_glowna_pokazuje_filmy(self):
        response = self.client.get("/")
        self.assertContains(response, "Matrix")

    def test_szczegoly_filmu(self):
        response = self.client.get(f"/movie/{self.movie.id}/")
        self.assertEqual(response.status_code, 200)

    def test_nieistniejacy_film_zwraca_404(self):
        self.assertEqual(self.client.get("/movie/99999/").status_code, 404)

    def test_szczegoly_seansu(self):
        response = self.client.get(f"/screening/{self.screening.id}/")
        self.assertEqual(response.status_code, 200)

    def test_strona_rejestracji(self):
        self.assertEqual(self.client.get("/register/").status_code, 200)

    def test_moje_rezerwacje_wymagaja_logowania(self):
        response = self.client.get("/my/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])


class AuthTests(BaseTest):
    def test_rejestracja_tworzy_uzytkownika(self):
        response = self.client.post(
            "/register/",
            {"username": "nowy", "email": "nowy@example.com", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="nowy").exists())

    def test_rejestracja_odrzuca_slabe_haslo(self):
        self.client.post(
            "/register/",
            {"username": "slaby", "email": "slaby@example.com", "password": "123"},
        )
        self.assertFalse(User.objects.filter(username="slaby").exists())

    def test_rejestracja_odrzuca_zajety_login(self):
        self.client.post(
            "/register/",
            {"username": "anna", "email": "inny@example.com", "password": PASSWORD},
        )
        self.assertEqual(User.objects.filter(username="anna").count(), 1)

    # Strona logowania, której używa serwis: reverse("login") wskazuje /accounts/login/
    def test_strona_logowania(self):
        self.assertEqual(self.client.get("/accounts/login/").status_code, 200)

    def test_logowanie_poprawne_haslo(self):
        response = self.client.post("/accounts/login/", {"username": "anna", "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_logowanie_bledne_haslo(self):
        response = self.client.post("/accounts/login/", {"username": "anna", "password": "zle-haslo"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class ReservationTests(BaseTest):
    def book(self, seats, screening=None):
        screening = screening or self.screening
        return self.client.post(f"/screening/{screening.id}/book/", {"seats": seats})

    def test_rezerwacja_miejsc(self):
        self.login(self.anna)
        response = self.book(["1-1", "1-2"])
        self.assertRedirects(response, "/my/")
        self.assertEqual(Reservation.objects.filter(user=self.anna).count(), 2)

    def test_zajete_miejsce_nie_moze_byc_zarezerwowane_drugi_raz(self):
        self.login(self.anna)
        self.book(["2-2"])
        self.login(self.bob)
        self.book(["2-2"])
        self.assertEqual(Reservation.objects.filter(screening=self.screening).count(), 1)
        self.assertFalse(Reservation.objects.filter(user=self.bob).exists())

    def test_konflikt_nie_zapisuje_czesci_miejsc(self):
        self.login(self.anna)
        self.book(["3-3"])
        self.login(self.bob)
        self.book(["3-3", "3-4"])  # jedno zajęte, całość ma się wycofać
        self.assertFalse(Reservation.objects.filter(user=self.bob).exists())

    def test_miejsce_poza_sala_jest_ignorowane(self):
        self.login(self.anna)
        self.book(["99-99"])
        self.assertEqual(Reservation.objects.count(), 0)

    def test_nie_mozna_rezerwowac_seansu_ktory_sie_zaczal(self):
        self.login(self.anna)
        self.book(["1-1"], screening=self.past_screening)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_rezerwacja_wymaga_logowania(self):
        self.book(["1-1"])
        self.assertEqual(Reservation.objects.count(), 0)

    def test_anulowanie_wlasnej_rezerwacji(self):
        res = Reservation.objects.create(user=self.anna, screening=self.screening, seat_row=1, seat_col=1)
        self.login(self.anna)
        self.client.post(f"/reservation/{res.id}/cancel/")
        self.assertFalse(Reservation.objects.filter(id=res.id).exists())

    def test_nie_mozna_anulowac_cudzej_rezerwacji(self):
        res = Reservation.objects.create(user=self.anna, screening=self.screening, seat_row=1, seat_col=1)
        self.login(self.bob)
        self.client.post(f"/reservation/{res.id}/cancel/")
        self.assertTrue(Reservation.objects.filter(id=res.id).exists())


class RatingTests(BaseTest):
    def rate(self, stars):
        return self.client.post(f"/movie/{self.movie.id}/rate/", {"stars": stars})

    def test_zapis_oceny(self):
        self.login(self.anna)
        self.rate(8)
        self.assertEqual(Rating.objects.get(user=self.anna, movie=self.movie).stars, 8)

    def test_ponowna_ocena_nadpisuje_poprzednia(self):
        self.login(self.anna)
        self.rate(5)
        self.rate(9)
        self.assertEqual(Rating.objects.filter(user=self.anna, movie=self.movie).count(), 1)
        self.assertEqual(Rating.objects.get(user=self.anna, movie=self.movie).stars, 9)

    def test_ocena_spoza_zakresu_jest_odrzucona(self):
        self.login(self.anna)
        self.rate(11)
        self.rate(0)
        self.assertFalse(Rating.objects.exists())

    def test_ocena_wymaga_logowania(self):
        self.rate(7)
        self.assertFalse(Rating.objects.exists())


class CommentTests(BaseTest):
    def comment(self, body):
        return self.client.post(f"/movie/{self.movie.id}/comment/", {"body": body})

    def test_dodanie_komentarza(self):
        self.login(self.anna)
        self.comment("Świetny film")
        self.assertEqual(Comment.objects.filter(user=self.anna).count(), 1)

    def test_pusty_komentarz_jest_odrzucony(self):
        self.login(self.anna)
        self.comment("   ")
        self.assertEqual(Comment.objects.count(), 0)

    def test_zbyt_dlugi_komentarz_jest_odrzucony(self):
        self.login(self.anna)
        self.comment("a" * 1001)
        self.assertEqual(Comment.objects.count(), 0)

    def test_autor_moze_usunac_komentarz(self):
        c = Comment.objects.create(movie=self.movie, user=self.anna, body="x")
        self.login(self.anna)
        self.client.post(f"/comment/{c.id}/delete/")
        self.assertFalse(Comment.objects.filter(id=c.id).exists())

    def test_obcy_uzytkownik_nie_usunie_komentarza(self):
        c = Comment.objects.create(movie=self.movie, user=self.anna, body="x")
        self.login(self.bob)
        self.client.post(f"/comment/{c.id}/delete/")
        self.assertTrue(Comment.objects.filter(id=c.id).exists())

    def test_administrator_moze_usunac_cudzy_komentarz(self):
        c = Comment.objects.create(movie=self.movie, user=self.anna, body="x")
        staff = User.objects.create_user("moderator", "m@example.com", PASSWORD, is_staff=True)
        self.login(staff)
        self.client.post(f"/comment/{c.id}/delete/")
        self.assertFalse(Comment.objects.filter(id=c.id).exists())


class SeedTests(TestCase):
    def test_seed_tworzy_dane_i_jest_idempotentny(self):
        call_command("seed", verbosity=0)
        filmy = Movie.objects.count()
        seanse = Screening.objects.count()
        uzytkownicy = User.objects.count()
        self.assertGreater(filmy, 0)
        self.assertGreater(seanse, 0)

        call_command("seed", verbosity=0)  # drugi raz nie może się wywalić ani dublować danych
        self.assertEqual(Movie.objects.count(), filmy)
        self.assertEqual(Screening.objects.count(), seanse)
        self.assertEqual(User.objects.count(), uzytkownicy)
