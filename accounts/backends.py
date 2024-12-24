from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from common.models import LOGIN_SUCCESS, LOGIN_NOT_EXIST, LOGIN_NOT_MATCH, LOGIN_ATTEMPT_COUNT_EXCEEDED


class EmailBackend(ModelBackend):
    """
    이메일 로그인 백엔드
    """

    def authenticate(self, request, email=None, username=None, password=None, **kwargs):
        login_id = email or username
        result = None
        user = None

        if not login_id:
            return None

        UserModel = get_user_model()

        if login_id.isnumeric():
            login_field = 'mobile'
        else:
            login_field = 'email'

        user = UserModel.objects.get_active_users().filter(**{login_field: login_id}).last()
        if user:
            result = LOGIN_SUCCESS if user.check_password(password) else LOGIN_NOT_MATCH
        else:
            result = LOGIN_NOT_EXIST

        UserModel.LOGIN_ATTEMPT_MODEL.objects.create(
            user_id=login_id,
            device_info=kwargs['device_info'] if 'device_info' in kwargs else {},
            app_info=kwargs['app_info'] if 'app_info' in kwargs else {},
            result=result
        )

        if result == LOGIN_SUCCESS:
            return user
        return None
