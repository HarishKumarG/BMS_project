from django.utils import timezone
from rest_framework import serializers
from BMS_app.models import User, Movie, Theatre, Show, Booking, Screen, Payment, Seat


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = '__all__'

class TheatreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theatre
        fields = '__all__'

class ScreenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screen
        fields = '__all__'

class ShowSerializer(serializers.ModelSerializer):
    class Meta:
        model = Show
        fields = ['id', 'show_number', 'theatre', 'screen', 'movie', 'show_time', 'total_tickets', 'ticket_price', 'available_seats' ]

    def validate(self, data):
        screen = data.get('screen')
        theatre = data.get('theatre')
        show_time = data.get('show_time')

        # Ensure the selected screen belongs to the selected theatre
        if screen and screen.theatre != theatre:
            raise serializers.ValidationError(
                f"The selected Screen {screen.screen_number} does not belong to Theatre '{theatre.theatre_name}'.")

        # Check if a show is already scheduled at this time on the same screen
        if Show.objects.filter(screen=screen, show_time=show_time).exists():
            raise serializers.ValidationError("Another show is already scheduled at this time on this screen.")

        if show_time <= timezone.now():
            raise serializers.ValidationError("Show time must be in the future.")

        return data

class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ['id', 'seat_number', 'is_booked']

class BookingSerializer(serializers.ModelSerializer):
    booking_price = serializers.SerializerMethodField()
    seats = SeatSerializer(many=True, read_only=True)
    selected_seats = serializers.ListField(child=serializers.CharField(), write_only=True)

    class Meta:
        model = Booking
        fields = ['id','booking_name', 'theatre', 'show', 'nooftickets', 'selected_seats', 'seats', 'booking_price']

    def get_booking_price(self, obj):
        return obj.nooftickets * obj.show.ticket_price

    def validate(self, data):
        theatre = data.get('theatre')
        show = data.get('show')
        selected_seats = data.get('selected_seats')
        nooftickets = len(selected_seats)

        if show.theatre != theatre:
            raise serializers.ValidationError(f"Selected show '{show}' does not belong to the theatre '{theatre}'.")

        available_seats = Seat.objects.filter(show=show, seat_number__in=selected_seats, is_booked=False)
        if len(available_seats) != nooftickets:
            raise serializers.ValidationError("Some selected seats are already booked or invalid.")

        return data

    def create(self, validated_data):
        selected_seats = validated_data.pop('selected_seats')
        validated_data['nooftickets'] = len(selected_seats)
        booking = Booking.objects.create(**validated_data)

        seats = Seat.objects.filter(show=booking.show, seat_number__in=selected_seats, is_booked=False)
        for seat in seats:
            seat.is_booked = True
            seat.save()
            booking.seats.add(seat)

        return booking


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = ['id', 'user', 'booking', 'amount', 'payment_method', 'transaction_id', 'created_at', 'status']

    def get_amount(self, obj):
        return obj.amount

    def get_booking_price(self, obj):
        if obj.booking:
            return obj.booking.nooftickets * obj.booking.show.ticket_price
        return None
