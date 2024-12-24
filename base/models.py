from collections import OrderedDict

from harupy.text import String

from django.db import models
from django.utils import timezone

from common.utils import SlackWebhook, CachedProperties


# 글로벌 데이터 캐쉬 설정
anyman = CachedProperties()
anyman.slack = SlackWebhook()


class BannedWordManager(models.Manager):
    """
    금지어 매니져
    """
    def check_username(self, username):
        username = String(username).extract_readable()
        hangul = String(username).extract_readable(True)
        for banned in self.get_queryset().filter(banned_username=True):
            if String(banned.word).hangul_rate() > 90 and banned.word in hangul:
                return False
            if banned.word in username:
                return False
        return True

    def check_words(self, content):
        banned = []
        for word in self.get_queryset().filter(banned_mission=True).values_list('word', flat=True):
            if word in content:
                banned.append(word)
        return banned or False


class BannedWord(models.Model):
    """
    금지어
    """
    word = models.CharField('단어', max_length=20)
    banned_username = models.BooleanField('회원 닉네임에 적용', blank=True, default=True)
    banned_mission = models.BooleanField('미션 내용에 적용', blank=True, default=True)

    objects = BannedWordManager()

    class Meta:
        verbose_name = '금지어'
        verbose_name_plural = '금지어'

    def __str__(self):
        return self.word


class AreaManager(models.Manager):
    """
    지역 매니져
    """
    def _strip(self, string):
        return string.rstrip('특별시').rstrip('광역시').rstrip('특별자치시').rstrip('특별자치도')

    def _replace(self, string):
        return string.replace('충북', '충청북도').replace('충남', '충청남도').replace('전북', '전라북도').replace('전남', '전라남도')\
                .replace('경북', '경상북도').replace('경남', '경상남도')

    def search(self, area_string):
        qs = self.get_queryset()
        matches = None
        strings = area_string.split(' ')
        no_matches = strings[3:]
        strings = strings[:3]
        if len(strings) > 1:
            last = strings.pop()
            while last:
                query = {
                    'name__icontains': self._strip(last)
                }
                if len(strings) is not 0:
                    query.update({'parent__isnull': False})
                matches = qs.filter(**query)
                if matches.exists():
                    break
                no_matches.insert(0, last)
                last = strings.pop()

            if matches is not None and matches.exists():
                if strings:
                    start = self._replace(self._strip(strings[0]))
                    matches = matches.filter(parent__name__startswith=start)
                if matches.exists():
                    if matches.count() > 1:
                        last_match = matches.filter(name=last)
                        if last_match.count() == 1:
                            return last_match.first().id, ' '.join(no_matches)
                        anyman.slack.channel('anyman__80dev').script_msg(
                            '지역검색 오류 알림',
                            '이 내용으로 검색할 때 지역이 복수로 검출됨.\n>>> %s' % area_string \
                            + ''.join(['\n- ' + str(a) for a in matches])
                        )
                    return matches.first().id, ' '.join(no_matches)
        elif len(strings) == 1:
            rtn = self.search(area_string + ' 1')
            if rtn and rtn[0] is not None:
                return (rtn[0], '')
        anyman.slack.channel('anyman__80dev').script_msg(
            '지역검색 오류 알림',
            '이 내용으로 검색할 때 지역이 검출되지 않음.\n%s' % area_string,
        )
        return None, ' '.join(no_matches)


class Area(models.Model):
    """
    지역
    """
    parent = models.ForeignKey('self', verbose_name='상위 지역', null=True, blank=True,
                               related_name='children', on_delete=models.CASCADE)
    name = models.CharField('지역명', max_length=10)
    nearby = models.ManyToManyField('self', verbose_name='인근 지역', blank=True)

    objects = AreaManager()

    class Meta:
        verbose_name = '지역'
        verbose_name_plural = '지역'

    def __str__(self):
        name = self.name
        p = self.parent
        while p:
            name = p.name + ' ' + name
            p = p.parent
        return name

    @property
    def nearby_string(self):
        return ', '.join([str(n) for n in self.nearby.all()])
    nearby_string.fget.short_description = '인근지역'

    # def clean(self):
    #     if self.parent == self:
    #         raise ValidationError({'parent': '자신을 상위 지역으로 가질 수 없습니다.'})
    #     if hasattr(self, 'nearby') and self in self.nearby:
    #         raise ValidationError({'nearby': '자신을 인근 지역으로 가질 수 없습니다.'})
    #     return super(Area, self).clean()
    #
    # def save(self, *args, **kwargs):
    #     if hasattr(self, 'id'):
    #         self.full_clean()
    #     return super(Area, self).save(*args, **kwargs)


class PopupManager(models.Manager):
    """
    팝업 매니져
    """
    def current(self, location=''):
        now = timezone.now()
        qs = self.get_queryset().filter(is_active=True, start_datetime__lte=now, end_datetime__gte=now)
        if location:
            qs = qs.filter(location=location)
        return qs


class Popup(models.Model):
    """
    팝업 및 배너 모델
    """
    LOCATIONS = (
        ('user', '고객 메인'),
        ('helper', '헬퍼 메인'),
        ('cs', '고객센터'),
        ('user_popup', '고객 팝업'),
        ('helper_popup', '헬퍼 팝업'),
    )
    TARGET_TYPES = (
        ('view', '뷰'),
        ('link', '외부링크'),
        ('webview', '내장 웹뷰'),
        ('contact', '[게시물] 1:1문의'),
        ('partnership', '[게시물] 제휴/제안'),
        ('customer_notice', '[게시물] 공지(고객)'),
        ('helper_notice', '[게시물] 공지(헬퍼)'),
        ('customer_event', '[게시물] 이벤트(고객)'),
        ('helper_event', '[게시물] 이벤트(헬퍼)'),
        ('magazine', '[게시물] 매거진'),
        ('webtoon', '[게시물] 웹툰'),
        ('faq', '[게시물] FAQ'),
    )
    location = models.CharField('위치', max_length=15, choices=LOCATIONS)
    target_type = models.CharField('타겟 타입', max_length=15, choices=TARGET_TYPES)
    target_id = models.CharField('타겟 식별자', max_length=100)
    title = models.CharField('제목', max_length=100)
    content = models.TextField('내용', blank=True, default='')
    image = models.ImageField('이미지', null=True, blank=True)
    start_datetime = models.DateTimeField('시작 일시')
    end_datetime = models.DateTimeField('종료 일시')
    is_active = models.BooleanField('활성화', null=True, blank=True, default=True)

    objects = PopupManager()

    class Meta:
        verbose_name = '팝업 및 배너'
        verbose_name_plural = '팝업 및 배너'

    def __str__(self):
        return self.title

    @property
    def pre_link(self):
        return '/link/%%s/%s/' % self.id

    @property
    def is_live(self):
        return self.end_datetime > timezone.now() > self.start_datetime

    def get_location_display(self):
        return OrderedDict(self.LOCATIONS).get(self.location)

    get_location_display.short_description = '위치'

    def get_target_type_display(self):
        return OrderedDict(self.TARGET_TYPES).get(self.target_type)

    get_target_type_display.short_description = '타겟 타입'
