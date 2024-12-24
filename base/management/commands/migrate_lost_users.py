import requests
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand
from django.utils import timezone

from common.utils import BaseExcelImportConverter, UploadFileHandler
from base.models import Area
from accounts.models import User, Helper, ServiceTag
from anyman_migration.models import HelperAsIs
from missions.models import CustomerService


class HelperUserImportConverter(BaseExcelImportConverter):
    model = User
    columns = (
        (
            'h_uid',
            'password',
            'last_login',
            'created_datetime',
            'is_active',
            'email',
            'username',
            'date_of_birth',
            'gender',
            'is_push_allowed',
            'withdrew_datetime',
            'level_user',
            '_is_service_blocked',
            'is_helper_main',
            'mobile',
            '_auth_center',
            '_recommended_by',
        ),
    )
    yes_or_no = {
        'Y': True,
        'y': True,
        'N': False,
        'n': False,
        '': None
    }

    def set_field_h_uid(self, obj, value):
        if HelperAsIs.objects.filter(h_uid=value).exists():
            print('H_UID 중복 :', value)
            return None
        obj.h_uid = value
        return obj

    def set_field_password(self, obj, value):
        obj.password = value or 'sktsjfdlek'
        return obj

    def set_field_is_active(self, obj, value):
        obj.is_active = self.yes_or_no[value]
        return obj

    def set_field_gender(self, obj, value):
        obj.gender = self.yes_or_no[value]
        return obj

    def set_field_is_push_allowed(self, obj, value):
        obj.is_push_allowed = self.yes_or_no[value]
        return obj

    def set_field_level_user(self, obj, value):
        obj.level = int(value)
        return obj

    def set_field__is_service_blocked(self, obj, value):
        obj._is_service_blocked = self.yes_or_no[value]
        return obj

    def set_field_is_helper_main(self, obj, value):
        obj.is_helper_main = True
        return obj

    def set_field_mobile(self, obj, value):
        if self.model.objects.filter(mobile=value).exists():
            print('mobile 중복 :', value)
            return False
        obj.mobile = value
        return obj

    def post_save_sheet_0(self, obj):
        obj.user_h_uid.create(h_uid=obj.h_uid)
        obj.set_password(obj.password)
        obj.save()


class HelperImportConverter(BaseExcelImportConverter):
    model = Helper
    columns = (
        (),
        (
            'UID',
            'UserHP',
            'ErrandTel',
            'Point',
            'OutPoint',
            'ImportPoint',
            'ImportName',
            'Cash',
            'S_H',
            'E_H',
            'E_H_R',
            'AlarmErrand',
            'Bank',
            'BankNum',
            'BankUser',
            'AM_UserID',
            'RegID',
            'DeviceID',
            'OsVersion',
            'AppVersionCode',
            'AppVersionName',
            'AppModel',
            'AppDevice',
            'AppProduct',
            'IsAgree',
            'RegDate',
            'LastLoginDate',
            'IsUsing',
            'T_UserID',
            'T_UserPass',
            'T_UserName',
            'T_Birth',
            'T_SEX',
            'T_RecomID',
            'T_RecomName',
            'T_PIC',
            'T_PIC_SSN',
            'T_ADDR1',
            'T_ADDR2',
            'T_JOB',
            'T_INTRODUCE',
            'T_MISSION',
            'T_HAPPY',
            'T_MOVE',
            'T_MOVE_ETC',
            'T_JOINPATH',
            'T_TEL',
            'ConPath',
            'SNS_BLOG',
            'SNS_FACEBOOK',
            'SNS_INSTAGRAM',
            'SNS_TWITTER',
            'IsBlock',
            'BlockReason',
            'BlockDate',
            'BlockEndDate',
            'IsOut',
            'OutDate',
            'AgentID',
            'AuthorComment',
            'ADV_UID',
            'Character',
            'IsGuide',
            'IsEdit',
            'SendSMS_CT',
            'IngCancelCT',
            'IngCancelDate',
            'IngCancelReason',
            'ErrandCT',
            'ErrandCompleteCT',
            'ErrandCancelCT',
            'ErrandBiddingCT',
            'IsOpen',
            'MAP',
            'IsMatching',
            'IsNotice',
            'ErrandJumsu',
            'ErrandCommentCT'
        ),
    )
    yes_or_no = {
        'Y': True,
        'y': True,
        'N': False,
        'n': False,
        '': None
    }
    BANK_CODES = {
        'KDB산업은행': 2,
        '산업은행': 2,
        'IBK기업은행': 3,
        '국민은행': 4,
        '외환은행': 5,
        '수협중앙회': 7,
        '수협': 7,
        '농협(중앙회)': 11,
        '농협(단위농협)': 12,
        '우리은행': 20,
        'SC제일은행': 23,
        '한국씨티은행': 27,
        '씨티은행': 27,
        '시티은행': 27,
        '대구은행': 31,
        '부산은행': 32,
        '광주은행': 34,
        '제주은행': 35,
        '전북은행': 37,
        '경남은행': 39,
        'KEB하나은행': 81,
        '신한은행': 88,
        '새마을금고': 45,
        '신협중앙회': 48,
        '상호저축은행': 50,
        '폐퍼저축은행': 50,
        'HSBC은행': 54,
        '도이치은행': 55,
        '케이뱅크': 89,
        '카카오뱅크': 90,
        '카카오': 90,

        '농협': 11,
        '기업은행': 3,
        '국민': 4,
        '신한': 88,
        '하나은행': 81,
        '기업': 3,
        '우리': 20,
        '우체국': 71,

    }
    soo = User.objects.get(id=1)
    image_prefix = 'http://182.162.146.45/Member/Pic/'

    def set_field_UID(self, obj, value):
        try:
            legacy = HelperAsIs.objects.get(h_uid=value)
            obj.user_id = legacy.user_id
        except:
            obj.user_id = None
        return obj

    def set_field_UserHP(self, obj, value):
        if value and value != 'NULL':
            value = str(value)
            if not value.startswith('0'):
                value = '0' + value
            obj.UserHP = value
        else:
            obj.UserHP = None

        if not obj.user_id:
            try:
                user = User.objects.get(mobile=obj.UserHP)
            except:
                print('UID 및 휴대폰 번호로 유져 오브젝트를 찾을 수 없음')
                return None
            obj.user = user

        helpers = self.model.objects.filter(user_id=obj.user_id)
        if helpers.exists():
            print('이미 헬퍼로 등록됨 : %s' % helpers.values_list('id', flat=True))
            return None
        return obj

    def set_field_ErrandTel(self, obj, value):
        if value and value != 'NULL':
            value = str(value)
            if not value.startswith('0'):
                    value = '0' + value
        if obj.UserHP == value:
            value = None
        obj.ErrandTel = value
        return obj

    def set_field_T_TEL(self, obj, value):
        if value and value != 'NULL':
            value = str(value)
            if not value.startswith('0'):
                value = '0' + value
        if obj.UserHP == value or obj.ErrandTel == value:
            value = None
        obj.T_TEL = value
        return obj

    def set_field_RegDate(self, obj, value):
        if not value or value == 'NULL':
            value = timezone.now()
        obj.user.created_datetime = value
        obj.requested_datetime = value
        obj.accepted_datetime = value
        return obj

    def set_field_LastLoginDate(self, obj, value):
        if not value or value == 'NULL':
            value = None
        obj.user.last_login = value
        return obj

    def set_field_T_Birth(self, obj, value):
        if not value or value == 'NULL':
            value = None
        obj.user.date_of_birth = value
        return obj

    def set_field_T_ADDR1(self, obj, value):
        if value not in ('NULL', 'None', None):
            obj.address_area_id, obj.address_detail_1 = Area.objects.search(value)
        return obj

    def set_field_T_ADDR2(self, obj, value):
        obj.address_detail_2 = value if value and value != 'NULL' else ''
        return obj

    def set_field_T_INTRODUCE(self, obj, value):
        obj.introduction = value if value and value != 'NULL' else ''
        return obj

    def set_field_T_HAPPY(self, obj, value):
        obj.best_moment = value if value and value != 'NULL' else ''
        return obj

    def set_field_T_MOVE(self, obj, value):
        if value not in ('NULL', 'None', None):
            obj.means_of_transport = [t.strip() for t in value.split(',')]
        return obj

    # def set_field_T_MOVE_ETC(self, obj, value):
    #     if value not in ('NULL', 'None', None):
    #         print(value)
    #         raise ValueError()
    #     return obj

    def set_field_IsBlock(self, obj, value):
        obj.user._is_service_blocked = self.yes_or_no[value]
        return obj

    def set_field_BlockEndDate(self, obj, value):
        if obj.user._is_service_blocked and obj.BlockDate and value and value != 'NULL':
            start_datetime = obj.BlockDate or None
            obj.user.service_blocks.create(start_datetime=start_datetime, end_datetime=value)
        return obj

    def set_field_OutDate(self, obj, value):
        if self.yes_or_no[obj.IsOut]:
            obj.withdrew_datetime = value
        return obj

    def set_field_ErrandCompleteCT(self, obj, value):
        obj._additional_mission_done_count = value
        return obj

    def set_field_ErrandCancelCT(self, obj, value):
        obj._additional_mission_canceled_count = value
        return obj

    def set_field_T_JOB(self, obj, value):
        if value not in ('NULL', 'None', None):
            obj._job = value
        return obj

    def set_field_T_JOINPATH(self, obj, value):
        if value not in ('NULL', 'None', None):
            obj._joined_from = value
        return obj

    def post_save_sheet_1(self, obj):
        # 기본값 설정
        obj.is_profile_public = True
        obj.name = obj.user.username
        if not (obj.Point > 0 or obj.ErrandBiddingCT > 0):
            obj.accepted_datetime = None

        # 회원 오브젝트 업데이트
        obj.user.save()

        # 이미지 저장 (프로필)
        if obj.T_PIC and obj.T_PIC != 'NULL':
            response = requests.get(self.image_prefix + obj.T_PIC)
            ext = obj.T_PIC.split('.')[-1]
            filename = 'helper/' + '.'.join([str(obj.id), str(timezone.now().timestamp()), ext])
            with open('media/' + filename, 'wb') as fp:
                fp.write(response.content)
            obj.profile_photo = filename

        # 이미지 저장 (신분증)
        if obj.T_PIC_SSN and obj.T_PIC_SSN != 'NULL':
            response = requests.get(self.image_prefix + obj.T_PIC_SSN)
            ext = obj.T_PIC_SSN.split('.')[-1]
            filename = 'helper/' + '.'.join([str(obj.id), 'id', str(timezone.now().timestamp()), ext])
            with open('media/' + filename, 'wb') as fp:
                fp.write(response.content)
            obj.id_photo = filename

        obj.save()

        # 은행계좌 추가
        if obj.Bank and obj.BankNum and obj.Bank in self.BANK_CODES:
            obj.bank_accounts.create(
                bank_code=self.BANK_CODES[obj.Bank],
                number=obj.BankNum,
                name=obj.BankUser,
                created_datetime=obj.user.created_datetime
            )

        if obj.T_MISSION and obj.T_MISSION != 'NULL':
            for tag in str(obj.T_MISSION).split(','):
                tag_obj, _ = ServiceTag.objects.get_or_create(title=tag.strip()[:50])
                obj.services.add(tag_obj)

        # 블럭된 경우 화면에 표시
        if obj.user._is_service_blocked:
            print('블럭 유저 추가됨!! user id : %s' % obj.user.id)

        # 휴대폰 번호 정리
        numbers = []
        if obj.UserHP and obj.UserHP != obj.user.mobile:
            numbers.append(obj.UserHP)
        if obj.ErrandTel and obj.ErrandTel != obj.user.mobile:
            numbers.append(obj.ErrandTel)
        if obj.T_TEL and obj.T_TEL != obj.user.mobile:
            numbers.append(obj.T_TEL)

        # 상담내역에 기록
        content = '*** Migrated by Soo at %s' % timezone.now()
        for number in numbers:
            content += '\n*** 추가 전화번호 발견됨 : %s' % number
        obj.user.customer_services.create(created_user=self.soo, content=content)
        obj.save()


class Command(BaseCommand):
    """
    누락 헬퍼 데이터 마이그레이션 커맨드
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.user_importer = HelperUserImportConverter('web/migration_data/lost_users.xlsx')
        self.helper_importer = HelperImportConverter('web/migration_data/lost_users.xlsx')

    def handle(self, *args, **options):
        self.create_users()
        self.create_helpers()

    def create_users(self):
        self.user_importer.set_sheet(0)
        data = self.user_importer.make_objects()
        if data:
            print('%s users 추가됨' % len(data))
            print(data)

    def create_helpers(self):
        self.helper_importer.set_sheet(1)
        # self.helper_importer.print()
        data = self.helper_importer.make_objects()
        if data:
            print('%s helpers 추가됨' % len(data))
            print(data)
