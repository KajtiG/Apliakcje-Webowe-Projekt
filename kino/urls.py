from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('movie/<int:movie_id>/', views.movie_detail, name='movie'),
    path('movie/<int:movie_id>/rate/', views.rate_movie, name='rate'),
    path('movie/<int:movie_id>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('screening/<int:screening_id>/', views.screening_detail, name='screening'),
    path('screening/<int:screening_id>/book/', views.book_seats, name='book'),
    path('my/', views.my_reservations, name='my_reservations'),
    path('reservation/<int:res_id>/cancel/', views.cancel_reservation, name='cancel'),
]