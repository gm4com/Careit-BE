from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import jwt
from .models import User

class HelperTemporaryAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header:
            return None

        try:
            auth_token = auth_header
            payload = jwt.decode(auth_token, settings.HELPER_SECRET_KEY)
            user_id = payload['user_id']
            user = User.objects.get(pk=user_id)
            return (user, None)
        except (jwt.DecodeError, User.DoesNotExist):
            raise AuthenticationFailed('Invalid authentication token')