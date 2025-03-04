import functools
import uuid
import redis
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .authentication import CustomJWTAuthentication
from .models import User, Movie, Theatre, Screen, Show, Booking, Payment, Seat, BlockedSeat, Rating
from .permissions import IsCustomer, IsManager, IsCustomerOrManager
from .serializer import UserSerializer, MovieSerializer, TheatreSerializer, ShowSerializer, BookingSerializer, \
    ScreenSerializer, PaymentSerializer, SeatSerializer, BlockedSeatSerializer, RatingSerializer
from .utils import generate_jwt
from django.core.cache import cache
from django.db import connection
import time
from django.contrib.auth.hashers import check_password

redis_instance = redis.StrictRedis(host='127.0.0.1', port=6379, db=1)

#common views
class UserView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class =UserSerializer

#manager views
class MovieView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsManager]
    queryset = Movie.objects.all()
    serializer_class =MovieSerializer

class TheatreView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsManager]
    queryset = Theatre.objects.all()
    serializer_class = TheatreSerializer

class ScreenView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsManager]
    queryset = Screen.objects.all()
    serializer_class = ScreenSerializer

class ShowView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsManager]
    queryset = Show.objects.all()
    serializer_class = ShowSerializer

    def validate(self, data):
        screen = data.get('screen')
        theatre = data.get('theatre')
        show_time = data.get('show_time')

        if screen and screen.theatre != theatre:
            raise serializers.ValidationError(
                f"The selected Screen {screen.screen_number} does not belong to Theatre '{theatre.theatre_name}'.")

        if Show.objects.filter(screen=screen, show_time=show_time).exists():
            raise serializers.ValidationError("Another show is already scheduled at this time on this screen.")

        if show_time <= timezone.now():
            raise serializers.ValidationError("Show time must be in the future.")

        return data

#customer views
class MovieSearchView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        query = request.query_params.get('movie', '')

        if not query:
            return Response({"error": "Please provide a movie name to search."}, status=status.HTTP_400_BAD_REQUEST)

        movie = Movie.objects.filter(title__icontains=query).first()

        if not movie:
            return Response({"message": "No movies found."}, status=status.HTTP_404_NOT_FOUND)

        shows = Show.objects.filter(movie=movie).select_related("theatre", "screen")
        theatre_dict = {}

        for show in shows:
            theatre_name = show.theatre.theatre_name
            if theatre_name not in theatre_dict:
                theatre_dict[theatre_name] = {"theatre_name": theatre_name, "shows": []}

            theatre_dict[theatre_name]["shows"].append({
                "show_time": show.show_time,
                "available_seats": show.available_seats,
            })

        response_data = {
            "movie_name": movie.title,
            "language": movie.language,
            "genre": movie.genre,
            "certificate": movie.certificate,
            "theatres": list(theatre_dict.values())
        }

        return Response(response_data, status=status.HTTP_200_OK)

class BookingView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomer]
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

                blocked_seats = BlockedSeat.objects.filter(show=show, seat__seat_number__in=selected_seats)
                if blocked_seats.exists():
                    return Response({"error": "Some selected seats are blocked"},
                                    status=status.HTTP_400_BAD_REQUEST)

                available_seats = Seat.objects.select_for_update().filter(show=show, seat_number__in=selected_seats,is_booked=False)
                if len(available_seats) != len(selected_seats):
                    return Response({"error": "Some selected seats are already booked or invalid"},
                                    status=status.HTTP_400_BAD_REQUEST)

                booking = serializer.save()
                for seat in available_seats:
                    seat.is_booked = True
                    seat.save()
                    booking.seats.add(seat)

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
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomer]
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
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerOrManager]
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
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            user = User.objects.get(email=email)  # Fetch user by email
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

        if check_password(password, user.password):  # Check hashed password
            token = generate_jwt(user)
            return Response({'access_token': token, 'role': user.role}, status=status.HTTP_200_OK)

        return Response({'error': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

class SearchTheaterView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomer]

    def get(self, request):
        query = request.query_params.get('theatre', '')

        if not query:
            return Response({"error": "Please provide a theatre name to search."}, status=status.HTTP_400_BAD_REQUEST)

        theatre = Theatre.objects.filter(theatre_name__icontains=query).first()

        if not theatre:
            return Response({"message": "No theatres found."}, status=status.HTTP_404_NOT_FOUND)

        shows = Show.objects.filter(theatre=theatre).select_related("movie", "screen")
        movie_dict = {}

        for show in shows:
            movie_title = show.movie.title
            if movie_title not in movie_dict:
                movie_dict[movie_title] = {
                    "title": movie_title,
                    "language": show.movie.language,
                    "genre": show.movie.genre,
                    "certificate": show.movie.certificate,
                    "shows": []
                }

            movie_dict[movie_title]["shows"].append({
                "show_time": show.show_time,
                "available_seats": show.available_seats,
            })

        response_data = {
            "theatre_name": theatre.theatre_name,
            "location": theatre.location,
            "movies": list(movie_dict.values())
        }

        return Response(response_data, status=status.HTTP_200_OK)

class BlockedSeatView(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsManager]
    queryset = BlockedSeat.objects.all()
    serializer_class = BlockedSeatSerializer

    def reduce_available_seats(self, show, new_blocked_count):
        show.available_seats -= new_blocked_count
        show.save()

    def increase_available_seats(self, show, removed_seats_count):
        show.available_seats = min(show.available_seats + removed_seats_count, show.total_tickets)
        show.save()

    @action(detail=False, methods=["POST"])
    def mark_blocked(self, request):
        show_id = request.data.get("show")
        seat_numbers = request.data.get("seats", [])

        if not show_id or not seat_numbers:
            return Response({"error": "Show ID and seats are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            show = Show.objects.get(id=show_id)
        except Show.DoesNotExist:
            return Response({"error": "Invalid show ID."}, status=status.HTTP_400_BAD_REQUEST)

        seats = Seat.objects.filter(show=show, seat_number__in=seat_numbers)
        found_seat_numbers = set(seat.seat_number for seat in seats)

        missing_seats = list(set(seat_numbers) - found_seat_numbers)
        if missing_seats:
            return Response(
                {"error": "Some seats not found in this show.", "missing_seats": missing_seats},
                status=status.HTTP_400_BAD_REQUEST,
            )

        already_blocked = BlockedSeat.objects.filter(show=show, seat__in=seats).values_list("seat__seat_number", flat=True)
        new_seats_to_block = [seat for seat in seats if seat.seat_number not in already_blocked]

        BlockedSeat.objects.bulk_create([BlockedSeat(show=show, seat=seat) for seat in new_seats_to_block])

        self.reduce_available_seats(show, len(new_seats_to_block))

        return Response(
            {
                "message": "Seats marked as blocked.",
                "blocked_seats": [seat.seat_number for seat in new_seats_to_block],
                "already_blocked": list(already_blocked),
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["POST"])
    def remove_blocked(self, request):
        show_id = request.data.get("show")
        seat_numbers = request.data.get("seats", [])

        if not show_id or not seat_numbers:
            return Response({"error": "Show ID and at least one seat number are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not Show.objects.filter(id=show_id).exists():
            return Response({"error": "Invalid show ID."}, status=status.HTTP_400_BAD_REQUEST)

        blocked_seats = BlockedSeat.objects.filter(show_id=show_id, seat__seat_number__in=seat_numbers)

        if not blocked_seats.exists():
            return Response({"error": "None of the selected seats are marked as blocked."},
                            status=status.HTTP_400_BAD_REQUEST)

        removed_count = blocked_seats.count()
        print(f"Removing {removed_count} blocked seats from Show {show_id}")  # Debugging
        blocked_seats.delete()

        show = Show.objects.get(id=show_id)
        self.increase_available_seats(show, removed_count)

        return Response({"message": f"Blocked seats {seat_numbers} removed successfully."}, status=status.HTTP_200_OK)


class RatingView(viewsets.ModelViewSet):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsAuthenticated, IsCustomerOrManager]
    queryset = Rating.objects.all()
    serializer_class = RatingSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        booking_id = data.get("booking")

        if not booking_id:
            return Response({"error": "Booking ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            booking = Booking.objects.get(id=booking_id, booking_name=request.user)
        except Booking.DoesNotExist:
            return Response({"error": "Invalid booking or unauthorized access"}, status=status.HTTP_400_BAD_REQUEST)

        if Rating.objects.filter(booking=booking).exists():
            return Response({"error": "You have already rated this booking"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save(booking=booking)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

