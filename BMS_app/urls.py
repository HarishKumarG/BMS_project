from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from BMS_app.views import UserView, MovieView, TheatreView, BookingView, ScreenView, ShowView, PaymentView, SeatView

router = DefaultRouter()
router.register(r'users', UserView)
router.register(r'movies', MovieView)
router.register(r'theatres', TheatreView)
router.register(r'screens', ScreenView)
router.register(r'shows', ShowView)
router.register(r'bookings', BookingView)
router.register(r'payments', PaymentView)
router.register(r'seats', SeatView)

urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]