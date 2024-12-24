from django.core.management.base import BaseCommand
from django.utils import timezone

from common.utils import BaseExcelImportConverter
from accounts.models import User, Helper
from anyman_migration.models import HelperAsIs
from missions.models import Review


class ReviewImportConverter(BaseExcelImportConverter):
    model = Review
    columns = (
        (
            'h_uid',
            'date',
            'score',
            'm_num',
            'm_uid',
            'data',
            'anycode',
        ),
    )
    yes_or_no = {
        'Y': True,
        'y': True,
        'N': False,
        'n': False,
        '': None
    }
    default_created_user_id = User.objects.get(code='00000').id

    def set_field_h_uid(self, obj, value):
        legacy_helper = HelperAsIs.objects.filter(h_uid=value).last()
        if not legacy_helper:
            print('H_UID에 해당하는 유져 없음 :', value)
            return None
        obj.created_user_id = self.default_created_user_id
        obj._received_user = legacy_helper.user
        return obj

    def set_field_date(self, obj, value):
        date_strings = value.split()
        apm = date_strings.pop(1)
        if apm == '오후' and not date_strings[-1].startswith('12:'):
            time_strings = date_strings.pop()
            time_strings = time_strings.split(':')
            time_strings[0] = str(int(time_strings[0]) + 12)
            date_strings.append(':'.join(time_strings))
        obj.date = ' '.join(date_strings)
        return obj

    def set_field_score(self, obj, value):
        obj.stars = [value, value]
        return obj

    def set_field_data(self, obj, value):
        obj.content = value
        return obj

    def post_save_sheet_0(self, obj):
        obj._is_created_user_helper = False
        obj.save()
        obj.created_datetime = obj.date
        obj.save()


class Command(BaseCommand):
    """
    누락 헬퍼 데이터 마이그레이션 커맨드
    """

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        self.review_importer = ReviewImportConverter('web/migration_data/lost_reviews.xlsx')

    def handle(self, *args, **options):
        self.create_reviews()

    def create_reviews(self):
        self.review_importer.set_sheet(0)
        data = self.review_importer.make_objects()
        if data:
            print('%s reviews 추가됨' % len(data))
            print(data)
