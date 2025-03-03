from django.contrib import admin
from BMS_app.models import User, Movie, Theatre, Show, Booking, Payment, Screen, Seat, BlockedSeat

# Register your models here.
admin.site.register(User)
admin.site.register(Movie)
admin.site.register(Theatre)
admin.site.register(Screen)
admin.site.register(Show)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Seat)
admin.site.register(BlockedSeat)