# Kino – rezerwacja miejsc, oceny i komentarze

Prosta aplikacja web (Flask + SQLite) na laboratorium L1.

## Wymagania z zadania → gdzie to jest

| Wymaganie | Realizacja |
|---|---|
| Strona web z logowaniem (sesją) | `/register`, `/login`, `/logout`; sesja Flask (podpisane ciasteczko), hasła hashowane (`werkzeug.security`) |
| Interakcja z użytkownikiem | oceny 1–5 ★ i komentarze pod filmami (dodawanie, usuwanie własnych) |
| Baza danych | SQLite (`kino.db`, tworzona automatycznie przy pierwszym starcie) |
| Technologia | Python 3 + Flask + szablony Jinja2 |

Dodatkowo: rezerwacja miejsc na seans (plan sali, wiele miejsc naraz, anulowanie, lista „Moje rezerwacje”).

## Uruchomienie

```bash
pip install -r requirements.txt
python app.py
```

Aplikacja działa pod adresem http://127.0.0.1:5000. Przy pierwszym uruchomieniu baza dostaje 4 przykładowe filmy z seansami w najbliższych dniach.


## Struktura

```
app.py              # cała logika: baza, sesja, trasy
templates/          # base, index, movie, screening, my, login, register
static/style.css    # style
requirements.txt
```

## Baza danych

- `users` – konta (login, hash hasła)
- `movies` – filmy
- `screenings` – seanse (film, data, sala, liczba rzędów/miejsc)
- `reservations` – zarezerwowane miejsca; UNIQUE (screening_id, seat_row, seat_col) gwarantuje, że to samo miejsce nie zostanie zarezerwowane dwa razy
- `ratings` – jedna ocena użytkownika na film (klucz główny user_id + movie_id)
- `comments` – komentarze
