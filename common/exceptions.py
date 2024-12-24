from django.utils.translation import gettext_lazy as _

from rest_framework import exceptions as e
from rest_framework import status

from harupy.text import String


class APIException(e.APIException):

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code

        self.message = detail
        if not isinstance(detail, dict) and not isinstance(detail, list):
            detail = [detail]

        self.detail = e._get_error_details({code: detail}, code)
        self.code = code

    def as_md(self):
        return '\n\n> **%s**\n\n```\n{\n\n\t"code": "%s"\n\n\t"message": "%s"\n\n}\n\n```' % \
               (self.detail, self.code, self.detail)

    def as_p(self):
        val = self.message if type(self.message) is not str else '"' + self.message + '"'
        return '*\{"%s"\: %s\}*\n' % (self.code, val)


class ValidationError(APIException):
    """
    Validation error exception
    """
    default_detail = _('Invalid input.')
    default_code = 'invalid'
    status_code = status.HTTP_400_BAD_REQUEST


class AuthenticationFailed(APIException):
    """
    Authentication failed exception
    """
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _('Incorrect authentication credentials.')
    default_code = 'authentication_failed'


class PermissionDenied(APIException):
    """
    Permission denied exception
    """
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _('You do not have permission to perform this action.')
    default_code = 'permission_denied'


class NotFound(APIException):
    """
    Not found exception
    """
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _('Not found.')
    default_code = 'not_found'


class NotAcceptable(APIException):
    """
    Not found exception
    """
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = _('Not acceptable.')
    default_code = 'not_acceptable'


class Errors(object):
    """
    Error Collection
    """
    fields_invalid = ValidationError('필드가 올바르지 않습니다.', 'non_field_errors')
    invalid_code = ValidationError('코드가 잘못 입력되었습니다.', 'code')
    invalid_mobile = ValidationError('전화번호가 잘못 입력되었습니다.', 'number')
    invalid_ids = ValidationError('ids가 잘못 입력되었습니다.', 'ids')
    invalid_information = ValidationError('정보가 제대로 입력되지 않았습니다.', 'no_information')
    attempt_count_exceeded = AuthenticationFailed('로그인 시도횟수를 초과했습니다.', 'attempt_count_exceeded')
    no_active_account = AuthenticationFailed('로그인할 수 없는 계정입니다.', 'no_active_account')
    invalid_social_id = ValidationError('소셜 인증 아이디가 유효하지 않습니다.', 'invalid_social_id')
    invalid_social_type = ValidationError('소셜 인증 타입이 유효하지 않습니다.', 'invalid_social_type')
    invalid_email = ValidationError('이메일 형식이 유효하지 않습니다.', 'invalid_email')
    invalid_password = ValidationError('비밀번호를 정확히 입력해주세요.', 'invalid_password')
    invalid_recommended_by = ValidationError('추천인 정보가 잘못 입력되었습니다.', '_recommended_by')
    invalid_username = ValidationError('닉네임이 잘못 입력되었습니다.', 'username')
    invalid_due_datetime = ValidationError('미션일시가 잘못 입력되었습니다.', 'due_datetime')
    invalid_amount = ValidationError('입찰액이 잘못 입력되었습니다.', 'amount')
    invalid_verification = ValidationError('인증 id와 휴대폰 번호가 맞지 않습니다.', 'verification_id')
    not_found = NotFound('찾을 수 없습니다.', 'not_found')
    mission_state_not_allowed = PermissionDenied('현재의 미션 상태로는 허용되지 않는 액션입니다.', 'mission_state_not_allowed')
    helper_only = PermissionDenied('헬퍼 전용 메뉴입니다.', 'helper_only')
    permission_denied = PermissionDenied('권한이 없습니다.', 'permission_denied')
    allowed_only_one_record = NotAcceptable('중복이 허용되지 않습니다.', 'allowed_only_one_record')
    not_usable = NotAcceptable('사용할 수 없습니다.', 'not_usable')
    insufficient_balance = NotAcceptable('잔액이 부족합니다.', 'insufficient_balance')
    card_insufficient_balance = NotAcceptable('카드 한도가 초과되어 결제하지 못했습니다.', 'card_insufficient_balance')
    billing_not_completed = NotAcceptable('카드등록 처리가 완료되지 못했습니다.', 'billing_not_completed')
    payment_not_completed = NotAcceptable('결제 처리가 완료되지 못했습니다.', 'payment_not_completed')
    interaction_before_not_ended = NotAcceptable('이전 인터랙션이 종료되지 않았습니다.', 'interaction_before_not_ended')
    service_blocked = PermissionDenied('서비스가 차단된 회원입니다.', 'service_blocked')
    mobile_already_exist = PermissionDenied('이미 존재하는 휴대폰 번호입니다.', 'mobile_already_exist')
    timeout = NotAcceptable('시간이 초과되었습니다.', 'timeout')
    email_already_exist = PermissionDenied('이미 존재하는 이메일입니다.', 'email_already_exist')
    not_paid = PermissionDenied('결제되지 않았습니다.', 'not_paid')
    already_paid = PermissionDenied('이미 결제되었습니다.', 'already_paid')
    mission_already_done = NotAcceptable('미션 수행이 이미 완료되었습니다.', 'mission_already_done')
    bid_already_exist = NotAcceptable('이미 입찰되었습니다.', 'bid_already_exist')
    bidding_mission_exist = NotAcceptable('이미 올려주신 미션이 입찰중입니다.', 'bidding_mission_exist')
    bid_state_not_applied = NotAcceptable('낙찰 불가 상태입니다. 헬퍼가 입찰을 취소했을 수 있습니다.', 'bid_state_not_applied')
    bid_locked = NotAcceptable('고객이 결제를 시도하고 있는 중입니다. 결제가 완료 또는 취소될 때까지 입찰을 취소할 수 없습니다.', 'bid_locked')
    voucher_not_found = NotFound('존재하지 않는 상품권입니다.', 'voucher_not_found')
    voucher_not_usable = NotAcceptable('이 상품권은 사용할 수 없습니다. 사용 조건이 맞지 않거나 이미 사용한 상품권입니다.', 'voucher_not_usable')
    coupon_not_found = NotFound('존재하지 않는 쿠폰입니다.', 'coupon_not_found')
    coupon_not_usable = NotAcceptable('이 쿠폰은 등록이나 사용이 불가능합니다. 조건이 맞지 않거나 이미 사용한 쿠폰입니다.', 'coupon_not_usable')
    duplicated_request = NotAcceptable('중복된 요청입니다.', 'duplicated_request')
    ci_not_authenticated = NotAcceptable('인증이 필요합니다.', 'ci_not_authenticated')
    exist_user_blocked = NotAcceptable('서비스가 차단된 회원입니다. 차단이 해제된 후에 기존 계정으로 로그인하세요.', 'exist_user_blocked')
    exist_user_blocked_and_withdrew = NotAcceptable('서비스가 차단된 상태로 탈퇴하셨으며, 재가입할 수 없습니다.', 'exist_user_blocked_and_withdrew')
    user_already_exist = NotAcceptable('사용중인 계정이 있습니다. 기존에 사용하시던 아이디와 비밀번호로 로그인해주세요.', 'user_already_exist')
    inactivated_user = NotAcceptable('사용중이던 기존 계정이 비활성화된 상태입니다. 고객센터로 문의해주세요.', 'inactivated_user')
    not_tuesday = NotAcceptable('매주 화요일에만 출금가능', 'not_tuesday')

    @staticmethod
    def account_not_match(cnt):
        return AuthenticationFailed({'count': cnt}, 'account_not_match')

    @staticmethod
    def invalid_content(word=''):
        return ValidationError(word, 'content')

    @staticmethod
    def billing_failed(msg):
        return NotAcceptable(msg, 'billing_failed')

    @staticmethod
    def missing_required_field(field_name):
        return ValidationError(String(field_name).josa('는') + ' 필수 항목입니다.', 'missing_required_field')
