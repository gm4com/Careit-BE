import json

from rest_framework.permissions import *
from common import exceptions


class IsActiveUser(IsAuthenticated):
    """
    활성 회원 전체 허용
    """

    def has_permission(self, request, view):
        if not super(IsActiveUser, self).has_permission(request, view):
            raise exceptions.AuthenticationFailed(
                '자격 인증데이터(authentication credentials)가 제공되지 않았습니다.',
                'no_credentials'
            )
        if not request.user.is_active or request.user.is_withdrawn:
            raise exceptions.PermissionDenied(
                '비활성화되거나 탈퇴된 회원',
                'deactivated'
            )
        return True


class IsValidUser(IsActiveUser):
    """
    블록되지 않은 회원 허용
    """

    def has_permission(self, request, view):
        if super(IsValidUser, self).has_permission(request, view) \
               and not request.user.is_service_blocked:
            return True
        raise exceptions.PermissionDenied(
            json.dumps(request.user.blocked_info),
            'service_blocked'
        )


class IsHelper(IsValidUser):
    """
    헬퍼 허용
    """

    def has_permission(self, request, view):
        if super(IsHelper, self).has_permission(request, view) \
                and request.user.is_helper:
            return True
        raise exceptions.PermissionDenied(
            '헬퍼 전용',
            'helpers_only'
        )


class IsAdminUser(IsValidUser):
    """
    관리자 회원 허용
    """

    def has_permission(self, request, view):
        if super(IsAdminUser, self).has_permission(request, view) \
                and request.user.is_staff:
            return True
        raise exceptions.PermissionDenied(
            '관리자 전용',
            'admin_only'
        )
