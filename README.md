1. Po sklonowaniu repozytorium aby odpalić aplikację tworzymy środowisko wirtualne:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
2. Następnie kongifurujemy bazę danych np w pgadmin4:

Tworzymy nową baze

w pliku config/settings.py i w sekcji DATABASES dostosuj NAME, USER (domyślnie postgres) oraz PASSWORD do swoich danych

3. Migracja i uruchomienie:

```bash
python manage.py migrate
```
Dodanie konta admin:
```bash
python manage.py createsuperuser
```
Uzupenienie bazy danych przykadowymi danymi:
```bash
python manage.py seed
```

```bash
python manage.py runserver
```
