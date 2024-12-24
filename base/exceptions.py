import enum

from common.exceptions import NotAcceptable


class ExternalErrors(enum.Enum):
    """
    외부 미션 에러 메세지
    """
    WRONG_REQUEST = '잘못된 요청입니다.'
    NO_FIELD = '필요한 필드가 없습니다.'
    VERIFICATION_NOT_FOUND = '휴대폰 인증정보를 확인할 수 없습니다.'
    ADDRESS_TRANSFORM_FAILED = '주소 인식에 실패했습니다.'
    MISSION_TRANSFORM_FAILED = '미션 자동변환에 실패했습니다. 고객센터로 문의 바랍니다.'
    DUE_DATETIME_OVER = '미션일시가 맞지 않습니다.'
    MISSION_REQUEST_FAILED = '미션을 헬퍼에게 요청하지 못했습니다. 고객센터로 문의 바랍니다.'

    @property
    def exception(self):
        return NotAcceptable(self.value, self.name.lower())
