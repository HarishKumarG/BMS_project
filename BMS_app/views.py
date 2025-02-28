import functools
import uuid
import redis
from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .authentication import CustomJWTAuthentication
from .models import User, Movie, Theatre, Screen, Show, Booking, Payment, Seat
from .serializer import UserSerializer, MovieSerializer, TheatreSerializer, ShowSerializer, BookingSerializer, \
    ScreenSerializer, PaymentSerializer, SeatSerializer
from .utils import generate_jwt
from django.core.cache import cache
from django.db import connection
import time
redis_instance = redis.StrictRedis(host='127.0.0.1', port=6379, db=1)



class UserView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class =UserSerializer

class MovieView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = Movie.objects.all()
    serializer_class =MovieSerializer

class TheatreView(viewsets.ModelViewSet):
    queryset = Theatre.objects.all()
    serializer_class = TheatreSerializer

class ScreenView(viewsets.ModelViewSet):
    queryset = Screen.objects.all()
    serializer_class = ScreenSerializer

class ShowView(viewsets.ModelViewSet):
    queryset = Show.objects.all()
    serializer_class = ShowSerializer


class BookingView(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            show = serializer.validated_data['show']
            selected_seats = serializer.validated_data['selected_seats']

            with transaction.atomic():
                show.refresh_from_db()

                available_seats = Seat.objects.filter(show=show, seat_number__in=selected_seats, is_booked=False)
                if len(available_seats) != len(selected_seats):
                    return Response({"error": "Some selected seats are already booked or invalid."},
                                    status=status.HTTP_400_BAD_REQUEST)

                booking = serializer.save()
                for seat in available_seats:
                    seat.is_booked = True
                    seat.save()
                    booking.seats.add(seat)
                show.available_seats -= len(selected_seats)
                show.save()

            return Response({"message": "Booking successful!", "data": BookingSerializer(booking).data},
                            status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def cancel(self, request, pk=None):
        try:
            booking = self.get_object()
            booking.cancel_booking()
            return Response({"message": "Booking canceled and seats restored."}, status=status.HTTP_200_OK)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=status.HTTP_404_NOT_FOUND)

class PaymentView(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        booking_id = data.get("booking")

        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"error": "Invalid booking ID"}, status=status.HTTP_400_BAD_REQUEST)

        if Payment.objects.filter(booking=booking).exists():
            return Response({"error": "Payment already exists for this booking"}, status=status.HTTP_400_BAD_REQUEST)

        transaction_id = str(uuid.uuid4())

        payment = Payment.objects.create(
            user=booking.booking_name,
            booking=booking,
            amount= booking.nooftickets * booking.show.ticket_price,
            payment_method=data.get("payment_method"),
            status=data.get("status"),
            transaction_id=transaction_id,
        )
        if payment.status == "completed":
            return Response(
                {"message": "Payment successful! Booking Confirmed", "data": PaymentSerializer(payment).data},
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(
                {"message": "Payment not confirmed!", "data": PaymentSerializer(payment).data},
                status=status.HTTP_201_CREATED
            )

def log_db_queries(f):
    @functools.wraps(f)
    def new_f(*args, **kwargs):
        start_time = time.time()

        connection.queries_log.clear()

        res = f(*args, **kwargs)

        end_time = time.time()
        duration = (end_time - start_time) * 1000.0

        print("-" * 80)
        print(f"TOTAL QUERIES: {len(connection.queries)}")
        for query in connection.queries:
            print(f"SQL: {query['sql']}\nTIME: {query['time']}s")
        print(f"Total execution time: {duration:.3f} ms")
        print("-" * 80)

        return res
    return new_f


class SeatView(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer

    def get_queryset(self):
        show_id = self.request.query_params.get('show_id')
        if show_id:
            return Seat.objects.filter(show_id=show_id)
        return Seat.objects.all()

    @action(detail=False, methods=['get'])
    @log_db_queries
    def available_seats(self, request):
        show_id = request.query_params.get('show_id')
        if not show_id:
            return Response({"error": "Show ID is required"}, status=400)

        cache_key = f"available_seats_{show_id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return Response(cached_data)

        seats = Seat.objects.filter(show_id=show_id, is_booked=False)
        serializer = self.get_serializer(seats, many=True)

        cache.set(cache_key, serializer.data, timeout=60*60)

        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def booked_seats(self, request):
        show_id = request.query_params.get('show_id')
        if not show_id:
            return Response({"error": "Show ID is required"}, status=400)
        seats = Seat.objects.filter(show_id=show_id, is_booked=True)
        serializer = self.get_serializer(seats, many=True)
        return Response(serializer.data)


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # Authenticate the user
        user = authenticate(username=username, password=password)

        if user is not None:
            # Generate a JWT token for the user
            token = generate_jwt(user)
            return Response({'access_token': token}, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)


