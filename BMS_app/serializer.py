from dataclasses import fields
from django.utils import timezone
from rest_framework import serializers
from BMS_app.models import User, Movie, Theatre, Show, Booking, Screen, Payment, Seat, BlockedSeat, Rating
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

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="booking.booking_name.username", read_only=True)
    movie = serializers.CharField(source="booking.show.movie.title", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "booking", "user", "movie", "rating", "review"]
        read_only_fields = ["id", "user", "movie"]


class TheatreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Theatre
        fields = '__all__'

class ScreenSerializer(serializers.ModelSerializer):
    theatre_id = serializers.PrimaryKeyRelatedField(queryset=Theatre.objects.all(), source="theatre", write_only=True)

    theatre_name = serializers.CharField(source="theatre.theatre_name", read_only=True)

    class Meta:
        model = Screen
        fields = [
            "id", "screen_number", "theatre_name", "theatre_id"
        ]

class ShowSerializer(serializers.ModelSerializer):
    theatre_id = serializers.PrimaryKeyRelatedField(queryset=Theatre.objects.all(), source="theatre", write_only=True)
    movie_id = serializers.PrimaryKeyRelatedField(queryset=Movie.objects.all(), source="movie", write_only=True)

    theatre_name = serializers.CharField(source="theatre.theatre_name", read_only=True)
    movie = serializers.CharField(source="movie.title", read_only=True)

    class Meta:
        model = Show
        fields = [
            "id", "show_number", "theatre_id", "theatre_name", "screen", "movie_id", "movie", "show_time", "total_tickets",
            "ticket_price", "available_seats"
        ]

class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ['id', 'seat_number', 'is_booked']

class BookingSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="booking_name.username", read_only=True)
    email = serializers.EmailField(source="booking_name.email", read_only=True)
    mobile = serializers.CharField(source="booking_name.mobile", read_only=True)
    theatre_name = serializers.CharField(source="theatre.theatre_name", read_only=True)
    theatre_location = serializers.CharField(source="theatre.location", read_only=True)
    show_number = serializers.IntegerField(source="show.id", read_only=True)
    screen = serializers.IntegerField(source="show.screen.screen_number", read_only=True)
    movie = serializers.CharField(source="show.movie.title", read_only=True)
    show_time = serializers.DateTimeField(source="show.start_time", format="%d-%m-%Y %H:%M:%S", read_only=True)
    seats = serializers.SerializerMethodField()
    booking_price = serializers.SerializerMethodField()

    def get_seats(self, obj):
        return [seat.seat_number for seat in obj.seats.all()]

    booking_name_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source="booking_name", write_only=True
    )
    theatre_id = serializers.PrimaryKeyRelatedField(queryset=Theatre.objects.all(), source="theatre", write_only=True)
    show_id = serializers.PrimaryKeyRelatedField(queryset=Show.objects.all(), source="show", write_only=True)
    selected_seats = serializers.ListField(child=serializers.CharField(), write_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "username", "email", "mobile", "theatre_name", "theatre_location", "movie", "show_number", "screen",  "show_time",
            "nooftickets", "seats", "booking_price", "booking_name_id", "theatre_id", "show_id", "selected_seats"
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
        show = validated_data["show"]
        seats = Seat.objects.filter(show=booking.show, seat_number__in=selected_seats, is_booked=False)
        for seat in seats:
            seat.is_booked = True
            seat.save()
            booking.seats.add(seat)
        show.available_seats -= len(selected_seats)
        show.save()
        print(show.available_seats)
        print(len(selected_seats))

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