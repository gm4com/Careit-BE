from django.utils.timezone import timedelta


USER_CODE_STRINGS = 'ABCDFGHJKLMNPQRTUVWXYZ346789'


MALE = False
FEMALE = True
GENDERS = [
    (MALE, '남자'),
    (FEMALE, '여자'),
    (None, '- 선택 안함 -')
]


WITHDRAW_GRACE = timedelta(days=7)


USER_STATUS = (
    ('withdrew', '탈퇴'),
    ('service_blocked', '차단'),
    ('deactivated', '비활성화'),
    ('customer', '고객'),
    ('helper', '헬퍼'),
    ('helper_requested', '헬퍼 신청됨'),
    ('helper_rejected', '헬퍼승인 거부됨'),
)


HELPER_REQUEST_STATUS = (
    ('requested', '신청됨'),
    ('accepted', '승인됨'),
    ('rejected', '거부됨'),
    ('deactivated', '비활성화'),
    ('requested_again', '재신청됨'),
)


BANK_CODES = (
    (2, '산업은행'),
    (3, '기업은행'),
    (4, '국민은행'),
    (5, 'KEB하나은행'),
    (7, '수협은행'),
    (10, '농협은행'),
    (12, '농협중앙회'),
    (20, '우리은행'),
    (21, '신한은행'),
    (23, 'SC제일은행'),
    (27, '한국씨티은행'),
    (31, '대구은행'),
    (32, '부산은행'),
    (34, '광주은행'),
    (35, '제주은행'),
    (37, '전북은행'),
    (39, '경남은행'),
    (45, '새마을금고중앙회'),
    (47, '신협중앙회'),
    (50, '상호저축은행'),
    (54, 'HSBC은행'),
    (55, '도이치은행'),
    (60, 'BOA은행'),
    (62, '중국공상은행'),
    (64, '산림조합중앙회'),
    (71, '우체국'),
    (89, 'K뱅크'),
    (90, '카카오뱅크'),
    (92, '토스뱅크'),
    (99, '금융결제원'),
    (209, '유안타증권'),
    (218, 'KB증권'),
    (225, 'IBK투자증권'),
    (230, '미래에셋증권'),
    (238, '미래에셋대우'),
    (240, '삼성증권'),
    (243, '한국투자증권'),
    (247, 'NH투자증권'),
    (261, '교보증권'),
    (262, '하이투자증권'),
    (263, '현대차투자증권'),
    (264, '키움증권'),
    (265, '이베스트투자증권'),
    (266, 'SK증권'),
    (267, '대신증권'),
    (268, '메리츠종합금융증권'),
    (269, '한화투자증권'),
    (270, '하나금융투자'),
    (271, '토스증권'),
    (278, '신한금융투자'),
    (279, '동부증권'),
    (280, '유진투자증권'),
    (288, '카카오페이증권'),
    (289, '(구)NH농협증권'),
    (290, '부국증권'),
    (291, '신영증권'),
    (292, '케이프투자증권'),
)


MISSION_STATUS = (
    ('draft', '미션 작성중'),
    ('bidding', '입찰중'),
    ('done', '수행완료'),
    ('done_and_canceled', '수행완료 후 취소'),
    ('admin_canceled', '관리자 직권취소'),
    ('user_canceled', '낙찰 전 취소'),
    ('timeout_canceled', '시간초과 자동취소'),
    ('won_and_canceled', '수행중 취소'),
    ('bid_and_canceled', '입찰 취소'),
    ('in_action', '수행중'),
    ('done_requested', '수행중 (완료요청)'),
    ('failed', '패찰'),
    ('applied', '입찰함'),
    ('not_applied', '지정헬퍼 미입찰'),
    ('mission_deactivated', '미션 비활성화'),
    ('waiting_assignee', '지정 헬퍼 입찰대기'),
    ('unknown', '알 수 없는 미션상태'),
)


MISSION_STATE_CLASSES = (
    ('draft', 'text-white bg-secondary'),
    ('bidding', 'bg-default'),
    ('done', 'text-white bg-success'),
    ('done_and_canceled', 'text-white bg-danger'),
    ('done_requested', 'text-white bg-primary'),
    ('admin_canceled', 'text-white bg-danger'),
    ('user_canceled', 'text-white bg-danger'),
    ('timeout_canceled', 'text-white bg-danger'),
    ('won_and_canceled', 'text-white bg-danger'),
    ('bid_and_canceled', 'text-white bg-warning'),
    ('in_action', 'text-white bg-primary'),
    ('failed', 'text-white bg-secondary'),
    ('applied', 'bg-default'),
    ('not_applied', 'text-white bg-secondary'),
    ('mideactivated', 'text-white bg-secondary'),
    ('waiting_assignee', 'text-white bg-dark'),
    ('unknown', 'text-white bg-warning'),
)
