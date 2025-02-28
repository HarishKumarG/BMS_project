import jwt
from datetime import datetime, timedelta
from django.conf import settings


def generate_jwt(user):
    payload = {
        'user_id': user.id,  # Store the user ID in the token payload
        'exp': datetime.utcnow() + timedelta(hours=1),  # Token expiration time (1 hour)
        'iat': datetime.utcnow(),  # Issued At time
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token