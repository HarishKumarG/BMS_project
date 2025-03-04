from tkinter.font import names

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from BMS_app.views import UserView, MovieView, TheatreView, ScreenView, ShowView, PaymentView, SeatView, \
    BookingView, MovieSearchView, LoginView, SearchTheaterView, BlockedSeatView, RatingView

router = DefaultRouter()
router.register(r'users', UserView)
router.register(r'movies', MovieView)
router.register(r'theatres', TheatreView)
router.register(r'screens', ScreenView)
router.register(r'shows', ShowView)
router.register(r'bookings', BookingView)
router.register(r'payments', PaymentView)
router.register(r'seats', SeatView)
router.register(r'blocked',BlockedSeatView)
router.register(r'ratings', RatingView)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    path('search/movie/', MovieSearchView.as_view(), name='movie-search'),
    path('search/theatre/', SearchTheaterView.as_view(), name='movie-search'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]