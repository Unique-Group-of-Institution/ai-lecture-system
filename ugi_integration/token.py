import jwt
from django.conf import settings

def verify_launch_token(token):
    try:
        payload = jwt.decode(
            token,
            settings.LMS_LAUNCH_SECRET,
            algorithms=['HS256'],
            audience=settings.LMS_LAUNCH_AUDIENCE,
            issuer=settings.LMS_LAUNCH_ISSUER,
            options={'require': ['exp', 'iat', 'sub', 'email']}
        )
        return payload
    except jwt.InvalidTokenError as e:
        print(f"Token verification failed: {e}")
        return None