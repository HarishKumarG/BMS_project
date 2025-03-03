import jwt
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication, exceptions
from django.contrib.auth.backends import ModelBackend
from .models import User

class CustomJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        token = auth_header.split(' ')[1] if ' ' in auth_header else None

        if not token:
            raise exceptions.AuthenticationFailed('Authorization token not found')

        try:
            # Decode the token with the secret key
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

            # Get the user ID from the payload and find the user
            user = User.objects.get(id=payload['user_id'])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')

        return (user, token)


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = User.objects.get(email=username)
            if user.check_password(password):  # Validate password
                return user
        except User.DoesNotExist:
            return None
