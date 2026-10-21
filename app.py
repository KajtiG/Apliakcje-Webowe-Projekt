import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, g, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "zmien-mnie-na-labach")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kino.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    year INTEGER,
    duration INTEGER
);
CREATE TABLE IF NOT EXISTS screenings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    starts_at TEXT NOT NULL,           -- 'YYYY-MM-DD HH:MM'
    hall TEXT NOT NULL,
    seat_rows INTEGER NOT NULL DEFAULT 6,
    seat_cols INTEGER NOT NULL DEFAULT 8
);
CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    screening_id INTEGER NOT NULL REFERENCES screenings(id) ON DELETE CASCADE,
    seat_row INTEGER NOT NULL,
    seat_col INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (screening_id, seat_row, seat_col)
);
CREATE TABLE IF NOT EXISTS ratings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    stars INTEGER NOT NULL CHECK (stars BETWEEN 1 AND 5),
    PRIMARY KEY (user_id, movie_id)
);
CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SEED_MOVIES = [
    ("Incepcja", "Złodziej wnikający w sny dostaje zadanie wszczepienia idei do umysłu celu.", 2010, 148),
    ("Interstellar", "Grupa astronautów wyrusza przez tunel czasoprzestrzenny, by ratować ludzkość.", 2014, 169),
    ("Matrix", "Haker odkrywa, że rzeczywistość jest symulacją stworzoną przez maszyny.", 1999, 136),
    ("Pulp Fiction", "Splecione historie gangsterów z Los Angeles.", 1994, 154),
]


# ---------- baza danych ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM movies").fetchone()[0] == 0:
        today = datetime.now().replace(minute=0, second=0, microsecond=0)
        for title, desc, year, dur in SEED_MOVIES:
            cur = db.execute(
                "INSERT INTO movies (title, description, year, duration) VALUES (?,?,?,?)",
                (title, desc, year, dur))
            for day, hour, hall in [(1, 17, "Sala 1"), (1, 20, "Sala 2"), (2, 18, "Sala 1"), (3, 21, "Sala 3")]:
                t = (today + timedelta(days=day)).replace(hour=hour)
                db.execute(
                    "INSERT INTO screenings (movie_id, starts_at, hall) VALUES (?,?,?)",
                    (cur.lastrowid, t.strftime("%Y-%m-%d %H:%M"), hall))
    db.commit()
    db.close()


# ---------- sesja / logowanie ----------
@app.before_request
def load_user():
    g.user = None
    uid = session.get("user_id")
    if uid is not None:
        g.user = get_db().execute("SELECT id, username FROM users WHERE id = ?", (uid,)).fetchone()
        if g.user is None:
            session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Musisz się zalogować.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 6:
            flash("Login min. 3 znaki, hasło min. 6 znaków.", "error")
        else:
            try:
                db = get_db()
                db.execute("INSERT INTO users (username, password_hash) VALUES (?,?)",
                           (username, generate_password_hash(password)))
                db.commit()
                flash("Konto utworzone. Możesz się zalogować.", "ok")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("Taki użytkownik już istnieje.", "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("index"))
        flash("Nieprawidłowy login lub hasło.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- filmy, oceny, komentarze ----------
@app.route("/")
def index():
    movies = get_db().execute("""
        SELECT m.*, ROUND(AVG(r.stars), 1) AS avg_rating, COUNT(r.stars) AS votes
        FROM movies m LEFT JOIN ratings r ON r.movie_id = m.id
        GROUP BY m.id ORDER BY m.title
    """).fetchall()
    return render_template("index.html", movies=movies)


@app.route("/movie/<int:movie_id>")
def movie(movie_id):
    db = get_db()
    m = db.execute("""
        SELECT m.*, ROUND(AVG(r.stars), 1) AS avg_rating, COUNT(r.stars) AS votes
        FROM movies m LEFT JOIN ratings r ON r.movie_id = m.id
        WHERE m.id = ? GROUP BY m.id
    """, (movie_id,)).fetchone()
    if m is None:
        abort(404)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    screenings = db.execute(
        "SELECT * FROM screenings WHERE movie_id = ? AND starts_at > ? ORDER BY starts_at",
        (movie_id, now)).fetchall()
    comments = db.execute("""
        SELECT c.*, u.username FROM comments c JOIN users u ON u.id = c.user_id
        WHERE c.movie_id = ? ORDER BY c.id DESC
    """, (movie_id,)).fetchall()
    my_rating = None
    if g.user:
        row = db.execute("SELECT stars FROM ratings WHERE user_id = ? AND movie_id = ?",
                         (g.user["id"], movie_id)).fetchone()
        my_rating = row["stars"] if row else None
    return render_template("movie.html", movie=m, screenings=screenings,
                           comments=comments, my_rating=my_rating)


@app.route("/movie/<int:movie_id>/rate", methods=["POST"])
@login_required
def rate(movie_id):
    try:
        stars = int(request.form.get("stars", ""))
    except ValueError:
        abort(400)
    if not 1 <= stars <= 5:
        abort(400)
    db = get_db()
    if db.execute("SELECT 1 FROM movies WHERE id = ?", (movie_id,)).fetchone() is None:
        abort(404)
    db.execute("""INSERT INTO ratings (user_id, movie_id, stars) VALUES (?,?,?)
                  ON CONFLICT(user_id, movie_id) DO UPDATE SET stars = excluded.stars""",
               (g.user["id"], movie_id, stars))
    db.commit()
    flash("Twoja ocena została zapisana.", "ok")
    return redirect(url_for("movie", movie_id=movie_id))


@app.route("/movie/<int:movie_id>/comment", methods=["POST"])
@login_required
def add_comment(movie_id):
    body = request.form.get("body", "").strip()
    if not body or len(body) > 1000:
        flash("Komentarz musi mieć od 1 do 1000 znaków.", "error")
        return redirect(url_for("movie", movie_id=movie_id))
    db = get_db()
    if db.execute("SELECT 1 FROM movies WHERE id = ?", (movie_id,)).fetchone() is None:
        abort(404)
    db.execute("INSERT INTO comments (movie_id, user_id, body, created_at) VALUES (?,?,?,?)",
               (movie_id, g.user["id"], body, datetime.now().strftime("%Y-%m-%d %H:%M")))
    db.commit()
    return redirect(url_for("movie", movie_id=movie_id) + "#komentarze")


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    db = get_db()
    c = db.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
    if c is None:
        abort(404)
    if c["user_id"] != g.user["id"]:
        abort(403)
    db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    db.commit()
    return redirect(url_for("movie", movie_id=c["movie_id"]) + "#komentarze")


# ---------- rezerwacje ----------
@app.route("/screening/<int:screening_id>")
def screening(screening_id):
    db = get_db()
    s = db.execute("""SELECT s.*, m.title FROM screenings s
                      JOIN movies m ON m.id = s.movie_id WHERE s.id = ?""",
                   (screening_id,)).fetchone()
    if s is None:
        abort(404)
    rows = db.execute("SELECT seat_row, seat_col, user_id FROM reservations WHERE screening_id = ?",
                      (screening_id,)).fetchall()
    taken = {(r["seat_row"], r["seat_col"]): r["user_id"] for r in rows}
    mine = {k for k, uid in taken.items() if g.user and uid == g.user["id"]}
    return render_template("screening.html", s=s, taken=taken, mine=mine)


@app.route("/screening/<int:screening_id>/book", methods=["POST"])
@login_required
def book(screening_id):
    db = get_db()
    s = db.execute("SELECT * FROM screenings WHERE id = ?", (screening_id,)).fetchone()
    if s is None:
        abort(404)
    if s["starts_at"] <= datetime.now().strftime("%Y-%m-%d %H:%M"):
        flash("Ten seans już się rozpoczął.", "error")
        return redirect(url_for("screening", screening_id=screening_id))

    seats = []
    for raw in request.form.getlist("seats"):
        try:
            r, c = (int(x) for x in raw.split("-"))
        except ValueError:
            abort(400)
        if not (1 <= r <= s["seat_rows"] and 1 <= c <= s["seat_cols"]):
            abort(400)
        seats.append((r, c))
    seats = sorted(set(seats))
    if not seats:
        flash("Wybierz co najmniej jedno miejsce.", "error")
        return redirect(url_for("screening", screening_id=screening_id))

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        with db:  # transakcja: wszystko albo nic
            for r, c in seats:
                db.execute("""INSERT INTO reservations
                              (user_id, screening_id, seat_row, seat_col, created_at)
                              VALUES (?,?,?,?,?)""",
                           (g.user["id"], screening_id, r, c, now))
    except sqlite3.IntegrityError:
        flash("Któreś z wybranych miejsc zostało właśnie zajęte. Wybierz inne.", "error")
        return redirect(url_for("screening", screening_id=screening_id))
    flash(f"Zarezerwowano miejsc: {len(seats)}.", "ok")
    return redirect(url_for("my_reservations"))


@app.route("/my")
@login_required
def my_reservations():
    rows = get_db().execute("""
        SELECT r.id, r.seat_row, r.seat_col, s.id AS screening_id, s.starts_at, s.hall, m.title
        FROM reservations r
        JOIN screenings s ON s.id = r.screening_id
        JOIN movies m ON m.id = s.movie_id
        WHERE r.user_id = ? ORDER BY s.starts_at, r.seat_row, r.seat_col
    """, (g.user["id"],)).fetchall()
    return render_template("my.html", reservations=rows)


@app.route("/reservation/<int:res_id>/cancel", methods=["POST"])
@login_required
def cancel(res_id):
    db = get_db()
    r = db.execute("SELECT * FROM reservations WHERE id = ?", (res_id,)).fetchone()
    if r is None:
        abort(404)
    if r["user_id"] != g.user["id"]:
        abort(403)
    db.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    db.commit()
    flash("Rezerwacja anulowana.", "ok")
    return redirect(url_for("my_reservations"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
