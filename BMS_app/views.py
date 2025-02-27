import uuid
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import User, Movie, Theatre, Screen, Show, Booking, Payment, Seat
from .serializer import UserSerializer, MovieSerializer, TheatreSerializer, ShowSerializer, BookingSerializer, \
    ScreenSerializer, PaymentSerializer, SeatSerializer


class UserView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class =UserSerializer

class MovieView(viewsets.ModelViewSet):
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

        # Calculate amount dynamically
        amount = booking.nooftickets * booking.show.ticket_price

        payment = Payment.objects.create(
            user=booking.booking_name,
            booking=booking,
            amount=amount,  # Use calculated amount
            payment_method=data.get("payment_method"),
            status=data.get("status"),
            transaction_id=transaction_id,
        )

        message = "Payment successful! Booking Confirmed" if payment.status == "completed" else "Payment not confirmed!"

        return Response(
            {"message": message, "data": PaymentSerializer(payment).data},
            status=status.HTTP_201_CREATED
        )

class SeatView(viewsets.ModelViewSet):
    queryset = Seat.objects.all()
    serializer_class = SeatSerializer

    def get_queryset(self):
        show_id = self.request.query_params.get('show_id')
        if show_id:
            return Seat.objects.filter(show_id=show_id)
        return Seat.objects.all()

    @action(detail=False, methods=['get'])
    def available_seats(self, request):
        show_id = request.query_params.get('show_id')
        if not show_id:
            return Response({"error": "Show ID is required"}, status=400)
        seats = Seat.objects.filter(show_id=show_id, is_booked=False)
        serializer = self.get_serializer(seats, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def booked_seats(self, request):
        show_id = request.query_params.get('show_id')
        if not show_id:
            return Response({"error": "Show ID is required"}, status=400)
        seats = Seat.objects.filter(show_id=show_id, is_booked=True)
        serializer = self.get_serializer(seats, many=True)
        return Response(serializer.data)
