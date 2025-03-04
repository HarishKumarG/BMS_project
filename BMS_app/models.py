from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

ROLE_CHOICES = (
    ('customer', 'Customer'),
    ('manager', 'Manager'),
)
class User(AbstractUser):
    username = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True)
    mobile = PhoneNumberField()
    location = models.CharField(max_length=100, blank=True)
    ismember = models.BooleanField(default=False)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    password = models.CharField(max_length=128, default=make_password("defaultpassword123"))  # Hashed default password


    groups = models.ManyToManyField(Group, related_name="custom_user_groups", blank=True)
    user_permissions = models.ManyToManyField(Permission, related_name="custom_user_permissions", blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'email', 'mobile', 'password']

    class Meta:
        ordering = ["id"]
        db_table = "User_details"

    def __str__(self):
        return self.username

class Movie(models.Model):
    title = models.CharField(max_length=100)
    language = models.CharField()
    genre = models.CharField()
    certificate = models.CharField(default="U")

    class Meta:
        ordering = ["id"]
        unique_together = (('title', 'language'),)
        db_table = "Movie_details"


    def __str__(self):
        return self.title

class Rating(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings")
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="ratings")
    rating = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    review = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["id"]
        unique_together = (('user', 'movie'),)
        db_table = "Rating_details"

    def __str__(self):
        return f"{self.movie.title} - Rating: {self.rating}"


class Theatre(models.Model):
    theatre_name = models.CharField()
    noofseats = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    location = models.CharField()

    class Meta:
        ordering = ["id"]
        unique_together = (('theatre_name', 'location'),)
        db_table = "Theatre_details"


    def __str__(self):
        return f"Id:{self.id} {self.theatre_name} {self.location}"


class Screen(models.Model):
    screen_number = models.PositiveIntegerField()
    theatre = models.ForeignKey("Theatre", on_delete=models.CASCADE, related_name="screens")

    class Meta:
        ordering = ["theatre", "screen_number"]
        unique_together = (('screen_number', 'theatre'),)
        db_table = "Screen_details"


    def __str__(self):
        return f"Screen {self.screen_number} - {self.theatre.theatre_name}"

class Show(models.Model):
    show_number = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(5)])
    movie = models.ForeignKey("Movie", on_delete=models.CASCADE, related_name='show_movie')
    theatre = models.ForeignKey("Theatre", on_delete=models.CASCADE, related_name='show_theatre')
    screen = models.ForeignKey("Screen", on_delete=models.CASCADE, related_name="screens", null=True, blank=True)
    show_time = models.DateTimeField()
    ticket_price = models.PositiveIntegerField(default=150, validators=[MinValueValidator(150), MaxValueValidator(200)])
    total_tickets = models.PositiveIntegerField(default=100)
    available_seats = models.PositiveIntegerField(default=100)
    class Meta:
        ordering = ["theatre", "screen", "show_number"]
        unique_together = (('screen', 'show_time', 'theatre'),)
        db_table = "Show_details"


    def __str__(self):
        return f"Show {self.show_number} - {self.movie.title} in {self.screen}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if it's a new instance
        super().save(*args, **kwargs)

        if is_new:  # Generate seats only if this is a new show
            self.generate_seats()

    def generate_seats(self):
        Seat.objects.filter(show=self).delete()
        rows = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        seats_per_row = 10  # Adjust based on theatre layout
        total_seats = min(self.theatre.noofseats, self.total_tickets)

        for i in range(total_seats):
            row = rows[i // seats_per_row]
            seat_num = f"{row}{(i % seats_per_row) + 1}"
            Seat.objects.create(show=self, seat_number=seat_num)

    def reduce_available_seats(self, no_of_seats):
        if self.available_seats >= no_of_seats:
            self.available_seats -= no_of_seats
            self.save()
            return True
        return False

class Booking(models.Model):
    booking_name = models.ForeignKey("User", on_delete=models.CASCADE, related_name='booking_user')
    nooftickets = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    theatre = models.ForeignKey("Theatre", on_delete=models.CASCADE, related_name='booking_theatre')
    show = models.ForeignKey("Show", on_delete=models.CASCADE, related_name='booking_show')
    seats = models.ManyToManyField("Seat", related_name="booked_seats")

    class Meta:
        db_table = "Booking_details"

    def __str__(self):
        return f"{self.id} {self.booking_name} Show: {self.show.show_number} Theatre: {self.theatre.theatre_name}"

    def cancel_booking(self):
        if self.show:
            self.seats.update(is_booked=False)

            self.show.available_seats += self.nooftickets
            self.show.save()
            self.delete()

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('upi', 'UPI'),
        ('net_banking', 'Net Banking'),
        ('wallet', 'Wallet'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "Payment_details"

    def __str__(self):
        return f"Payment {self.id} by User: {self.user.username} - {self.status}"

class Seat(models.Model):
    show = models.ForeignKey("Show", on_delete=models.CASCADE, related_name="seats")
    seat_number = models.CharField(max_length=5)
    is_booked = models.BooleanField(default=False)

    class Meta:
        unique_together = ("show", "seat_number")
        db_table = "Seat_details"

    def __str__(self):
        return f"{self.seat_number} - {'Booked' if self.is_booked else 'Available'}"

class BlockedSeat(models.Model):
    show = models.ForeignKey("Show", on_delete=models.CASCADE, related_name="blocked_seats")
    seat = models.ForeignKey("Seat", on_delete=models.CASCADE, related_name="blocked_in_show")

    class Meta:
        db_table = "BlockedSeat_details"
    def __str__(self):
        return f"Blocked: {self.seat.seat_number} in Show {self.show.id}"



