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
        password = request.POST.get('password', '')
        
        if len(username) < 3 or len(password) < 6:
            messages.error(request, "Login min. 3 znaki, hasło min. 6 znaków.")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Taki użytkownik już istnieje.")
        else:
            User.objects.create_user(username=username, password=password)
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
            next_url = request.GET.get('next', 'index')
            # Zapobieganie przekierowaniom poza obręb własnej domeny
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = '/'
            return redirect(next_url)
        else:
            messages.error(request, "Nieprawidłowy login lub hasło.")
            
    return render(request, 'login.html')

def logout_view(request):
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
        if 0 < len(body) <= 1000:
            Comment.objects.create(user=request.user, movie=movie, body=body)
        else:
            messages.error(request, "Komentarz musi mieć od 1 do 1000 znaków.")
    return redirect(f"{reverse('movie', args=[movie.id])}#komentarze")

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    movie_id = comment.movie.id
    if comment.user == request.user and request.method == 'POST':
        comment.delete()
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
            messages.success(request, f"Zarezerwowano miejsc: {len(seats_to_book)}.")
            return redirect('my_reservations')
        except IntegrityError:
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
        reservation.delete()
        messages.success(request, "Rezerwacja anulowana.")
    return redirect('my_reservations')