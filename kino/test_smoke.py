from django.contrib.auth import get_user_model
from django.test import TestCase


class SmokeTests(TestCase):
    def test_strona_glowna_dziala(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_logowanie_do_admina_jest_dostepne(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_admin_wymaga_logowania(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_panel_admina_dla_superusera(self):
        User = get_user_model()
        admin = User.objects.create_superuser(
            username="admin_test", email="admin@example.com", password="Test-pass-12345!"
        )
        # force_login omija formularz (i ewentualne django-axes), a sprawdza sam panel
        self.client.force_login(admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)