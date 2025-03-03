from django.utils import timezone
from rest_framework import serializers
from BMS_app.models import User, Movie, Theatre, Show, Booking, Screen, Payment, Seat, BlockedSeat
from django.contrib.auth.hashers import make_password


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'mobile', 'location', 'role', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

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
    show_time = serializers.DateTimeField(format="%d-%m-%Y %H:%M:%S")
    class Meta:
        model = Show
        fields = ['id', 'show_number', 'theatre', 'screen', 'movie', 'show_time', 'total_tickets', 'ticket_price', 'available_seats' ]

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

class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ['id', 'seat_number', 'is_booked']


class BookingSerializer(serializers.ModelSerializer):
    booking_name = UserSerializer(read_only=True)
    theatre = TheatreSerializer(read_only=True)
    show = ShowSerializer(read_only=True)
    seats = SeatSerializer(many=True, read_only=True)

    booking_name_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="booking_name", write_only=True)
    theatre_id = serializers.PrimaryKeyRelatedField(queryset=Theatre.objects.all(), source="theatre", write_only=True)
    show_id = serializers.PrimaryKeyRelatedField(queryset=Show.objects.all(), source="show", write_only=True)
    selected_seats = serializers.ListField(child=serializers.CharField(), write_only=True)

    booking_price = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id", "booking_name", "theatre", "show", "nooftickets", "selected_seats", "seats", "booking_price",
            "booking_name_id", "theatre_id", "show_id"
        ]

    def get_booking_price(self, obj):
        return obj.nooftickets * obj.show.ticket_price

    def validate(self, data):
        show = data["show"]
        theatre = data["theatre"]
        selected_seats = data.get("selected_seats", [])

        if show.theatre != theatre:
            raise serializers.ValidationError(f"Selected show '{show}' does not belong to the theatre '{theatre}'.")

        available_seats = Seat.objects.filter(show=show, seat_number__in=selected_seats, is_booked=False)
        if len(available_seats) != len(selected_seats):
            raise serializers.ValidationError("Some selected seats are already booked or invalid.")

        return data

    def create(self, validated_data):
        selected_seats = validated_data.pop("selected_seats")
        validated_data["nooftickets"] = len(selected_seats)
        booking = Booking.objects.create(**validated_data)

        seats = Seat.objects.filter(show=booking.show, seat_number__in=selected_seats, is_booked=False)
        for seat in seats:
            seat.is_booked = True
            seat.save()
            booking.seats.add(seat)

        return booking



class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.SerializerMethodField()

    booking = BookingSerializer(read_only=True)

    booking_details = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.all(), source="booking", write_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'booking', 'booking_details', 'amount', 'payment_method', 'transaction_id', 'created_at', 'status',]

    def get_amount(self, obj):
        return obj.amount

    def get_booking_price(self, obj):
        if obj.booking:
            return obj.booking.nooftickets * obj.booking.show.ticket_price
        return None

class BlockedSeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedSeat
        fields = "__all__"