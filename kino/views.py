from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Avg, Count
from django.utils import timezone
from .models import Movie, Screening, Reservation, Comment, Rating
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.urls import reverse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponse
from PIL import Image
import logging
import os

# Logger aplikacji - trafia na stdout (Container Apps -> Log Analytics)
logger = logging.getLogger("kino")

MAX_IMAGE_BYTES = 5 * 1024 * 1024
# Serwujemy tylko te typy (po rozszerzeniu) - bez SVG/HTML, żeby uniknąć XSS
IMAGE_CONTENT_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def _client_ip(request):
    """IP klienta zza Application Gateway (ostatni wpis X-Forwarded-For dodaje zaufane proxy)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = xff.split(",")[-1].strip() if xff else request.META.get("REMOTE_ADDR", "")
    return ip.rsplit(":", 1)[0] if ip.count(":") == 1 else ip  # App Gateway dopisuje :port


def _valid_image(f):
    """Sprawdza rozmiar i faktyczny format pliku (JPEG/PNG) - nie ufamy rozszerzeniu."""
    if f.size > MAX_IMAGE_BYTES:
        return False
    try:
        with Image.open(f) as im:
            im.verify()
            return im.format in ("JPEG", "PNG")
    except Exception:
        return False
    finally:
        f.seek(0)


def index(request):
    movies = Movie.objects.annotate(
        avg_rating=Avg('ratings__stars'),
        votes=Count('ratings')
    ).order_by('title')
    
    return render(request, 'index.html', {'movies': movies})

def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie.objects.annotate(
        avg_rating=Avg('ratings__stars'),
        votes=Count('ratings')
    ), id=movie_id)
    
    screenings = movie.screenings.filter(starts_at__gt=timezone.now()).order_by('starts_at')
    comments = movie.comments.select_related('user').order_by('-created_at')
    
    my_rating = None
    if request.user.is_authenticated:
        rating_obj = Rating.objects.filter(user=request.user, movie=movie).first()
        if rating_obj:
            my_rating = rating_obj.stars

    context = {
        'movie': movie,
        'screenings': screenings,
        'comments': comments,
        'my_rating': my_rating,
        'stars_range': range(1, 11)
    }
    return render(request, 'movie.html', context)

def screening_detail(request, screening_id):
    screening = get_object_or_404(Screening.objects.select_related('movie'), id=screening_id)
    
    # Pobieranie zajętych miejsc i przypisywanie ich do słownika wg współrzędnych
    reservations = Reservation.objects.filter(screening=screening)
    taken_seats = {(r.seat_row, r.seat_col): r.user_id for r in reservations}
    
    seating_grid = []
    for r in range(1, screening.seat_rows + 1):
        row_data = {'row_num': r, 'seats': []}
        for c in range(1, screening.seat_cols + 1):
            status = 'free'
            if (r, c) in taken_seats:
                if request.user.is_authenticated and taken_seats[(r, c)] == request.user.id:
                    status = 'mine'
                else:
                    status = 'taken'
            row_data['seats'].append({'col_num': c, 'status': status})
        seating_grid.append(row_data)

    return render(request, 'screening.html', {
        's': screening,
        'seating_grid': seating_grid
    })


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        try:
            validate_email(email)
            email_ok = True
        except ValidationError:
            email_ok = False

        if len(username) < 3:
            messages.error(request, "Login min. 3 znaki.")
        elif not email_ok:
            messages.error(request, "Podaj poprawny adres e-mail.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Taki użytkownik już istnieje.")
        elif User.objects.filter(email__iexact=email).exists():
            messages.error(request, "Ten adres e-mail jest już używany.")
        else:
            # Te same walidatory co przy resecie hasła (AUTH_PASSWORD_VALIDATORS)
            candidate = User(username=username, email=email)
            try:
                validate_password(password, user=candidate)
            except ValidationError as e:
                for msg in e.messages:
                    messages.error(request, msg)
            else:
                User.objects.create_user(username=username, email=email, password=password)
                logger.info("register ok user=%r ip=%s", username, _client_ip(request))
                messages.success(request, "Konto utworzone. Możesz się zalogować.")
                return redirect('login')

    return render(request, 'register.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            logger.info("login ok user=%r ip=%s", username, _client_ip(request))
            next_url = request.GET.get('next', 'index')
            # Zapobieganie przekierowaniom poza obręb własnej domeny
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = '/'
            return redirect(next_url)
        else:
            logger.warning("login failed user=%r ip=%s", username, _client_ip(request))
            messages.error(request, "Nieprawidłowy login lub hasło.")
            
    return render(request, 'login.html')

def logout_view(request):
    logger.info("logout user=%r", request.user.get_username())
    logout(request)
    return redirect('index')

@login_required
def rate_movie(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == 'POST':
        try:
            stars = int(request.POST.get('stars', 0))
            if 1 <= stars <= 10:
                Rating.objects.update_or_create(
                    user=request.user, movie=movie,
                    defaults={'stars': stars}
                )
                messages.success(request, "Twoja ocena została zapisana.")
        except ValueError:
            pass
    return redirect('movie', movie_id=movie.id)

@login_required
def add_comment(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == 'POST':
        body = request.POST.get('body', '').strip()
        image = request.FILES.get('image') # Pobranie obrazka
        
        if image and not _valid_image(image):
            messages.error(request, "Obrazek musi być plikiem JPEG lub PNG o rozmiarze do 5 MB.")
        elif 0 < len(body) <= 1000:
            comment = Comment.objects.create(user=request.user, movie=movie, body=body, image=image)
            logger.info("comment added id=%s movie=%s user=%r has_image=%s",
                        comment.id, movie.id, request.user.get_username(), bool(image))
        else:
            messages.error(request, "Komentarz musi mieć od 1 do 1000 znaków.")
    return redirect(f"{reverse('movie', args=[movie.id])}#komentarze")

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    movie_id = comment.movie.id
    
    # Sprawdzenie uprawnień (autor lub administrator)
    if request.user == comment.user or request.user.is_staff:
        if request.method == 'POST':
            logger.info("comment deleted id=%s by=%r", comment_id, request.user.get_username())
            comment.delete()
            messages.success(request, "Komentarz został pomyślnie usunięty.")
    else:
        logger.warning("comment delete denied id=%s by=%r", comment_id, request.user.get_username())
        messages.error(request, "Nie masz uprawnień do usunięcia tego komentarza.")
        
    return redirect(f"{reverse('movie', args=[movie_id])}#komentarze")

@login_required
def book_seats(request, screening_id):
    screening = get_object_or_404(Screening, id=screening_id)
    
    if screening.starts_at <= timezone.now():
        messages.error(request, "Ten seans już się rozpoczął.")
        return redirect('screening', screening_id=screening.id)

    if request.method == 'POST':
        raw_seats = request.POST.getlist('seats')
        seats_to_book = []
        for raw in raw_seats:
            try:
                r, c = map(int, raw.split('-'))
                if 1 <= r <= screening.seat_rows and 1 <= c <= screening.seat_cols:
                    seats_to_book.append((r, c))
            except ValueError:
                continue

        seats_to_book = list(set(seats_to_book))
        if not seats_to_book:
            messages.error(request, "Wybierz co najmniej jedno miejsce.")
            return redirect('screening', screening_id=screening.id)

        try:
            with transaction.atomic():
                for r, c in seats_to_book:
                    Reservation.objects.create(
                        user=request.user,
                        screening=screening,
                        seat_row=r,
                        seat_col=c
                    )
            logger.info("reservation created screening=%s user=%r seats=%s",
                        screening.id, request.user.get_username(), sorted(seats_to_book))
            messages.success(request, f"Zarezerwowano miejsc: {len(seats_to_book)}.")
            return redirect('my_reservations')
        except IntegrityError:
            logger.warning("reservation conflict screening=%s user=%r seats=%s",
                           screening.id, request.user.get_username(), sorted(seats_to_book))
            messages.error(request, "Któreś z wybranych miejsc zostało właśnie zajęte. Wybierz inne.")
            
    return redirect('screening', screening_id=screening.id)

@login_required
def my_reservations(request):
    reservations = Reservation.objects.filter(user=request.user).select_related('screening__movie').order_by('screening__starts_at', 'seat_row', 'seat_col')
    
    # Przekształcenie danych do formatu oczekiwanego przez szablon my.html
    res_list = [{
        'id': r.id,
        'seat_row': r.seat_row,
        'seat_col': r.seat_col,
        'screening_id': r.screening.id,
        'starts_at': r.screening.starts_at,
        'hall': r.screening.hall,
        'title': r.screening.movie.title
    } for r in reservations]

    return render(request, 'my.html', {'reservations': res_list})

@login_required
def cancel_reservation(request, res_id):
    reservation = get_object_or_404(Reservation, id=res_id)
    if request.method == 'POST' and reservation.user == request.user:
        logger.info("reservation cancelled id=%s user=%r", res_id, request.user.get_username())
        reservation.delete()
        messages.success(request, "Rezerwacja anulowana.")
    return redirect('my_reservations')

def custom_lockout_response(request, credentials, *args, **kwargs):
    logger.warning("account locked user=%r ip=%s", (credentials or {}).get("username"), _client_ip(request))
    messages.error(request, "Twoje konto zostało zablokowane z powodu zbyt wielu nieudanych prób logowania. Spróbuj ponownie za godzinę.")
    # Upewnij się, że 'login' to poprawna nazwa Twojej ścieżki logowania w urls.py
    return redirect(reverse('login'))


def healthz(request):
    """Probe dla Application Gateway i Container Apps - bez dotykania bazy."""
    return HttpResponse("ok", content_type="text/plain")


def comment_image(request, comment_id):
    """Obrazki z Blob Storage idą przez aplikację (Blob jest prywatny, bez dostępu z internetu)."""
    comment = get_object_or_404(Comment, id=comment_id)
    if not comment.image:
        raise Http404
    ctype = IMAGE_CONTENT_TYPES.get(os.path.splitext(comment.image.name)[1].lower())
    if ctype is None:
        raise Http404
    try:
        f = default_storage.open(comment.image.name, "rb")
    except FileNotFoundError:
        raise Http404
    resp = FileResponse(f, content_type=ctype)
    resp["Cache-Control"] = "private, max-age=3600"
    return resp
