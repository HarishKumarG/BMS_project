import jwt
from datetime import datetime, timedelta
from django.conf import settings


def generate_jwt(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=3),
        'iat': datetime.utcnow(),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token