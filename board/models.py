import re

from django.db import models
from django.conf import settings

from django_summernote.fields import SummernoteTextField

from common.utils import UploadFileHandler
from accounts.models import User, Helper, Area


BOARDS = (
    (1, '1:1 문의'),
    (2, '제휴/제안'),
    (3, '공지'),
    (4, '이벤트'),
    (5, '매거진'),
    (6, '웹툰'),
    (7, 'FAQ'),
    (11, '보도자료'),
)


BOARD_IDS = {
    'contact': 1,
    'partnership': 2,
    'notice': 3,
    'customer_notice': 3,
    'helper_notice': 3,
    'event': 4,
    'customer_event': 4,
    'helper_event': 4,
    'magazine': 5,
    'webtoon': 6,
    'faq': 7,
    'article': 11,
}


BOARD_FUNCTIONS = {
    1: ['attach', 'answer', 'user_create'],
    2: ['attach', 'answer', 'user_create'],
    3: ['title_image', 'location'],
    4: ['title_image', 'location', 'term'],
    5: ['title_image', 'comment'],
    6: ['title_image', 'comment'],
    7: ['answer'],
    11: ['title_image'],
}


class Writing(models.Model):
    """
    게시판 글 모델
    """
    board = models.PositiveSmallIntegerField('게시판', choices=BOARDS)
    title = models.CharField('제목', max_length=255)
    subtitle = models.CharField('부제목', max_length=100, blank=True, default='')
    content = SummernoteTextField('내용', blank=True)
    created_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='작성자', null=True, blank=True,
                                     related_name='writings', on_delete=models.SET_NULL)
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    updated_datetime = models.DateTimeField('수정일시', null=True, blank=True)
    viewed_count = models.PositiveIntegerField('조회수', blank=True, default=0)

    class Meta:
        verbose_name = verbose_name_plural = '게시글'

    def __str__(self):
        return self.title

    def read(self):
        self.viewed_count += 1
        self.save()
        return self

    def get_comments_display(self):
        return self.comments.all().count()
    get_comments_display.short_description = '코멘트'
    get_comments_display.admin_order_field = 'comments__count'

    @property
    def parsed_content(self):
        try:
            return re.sub(r'src\=\"\/media\/django\-summernote\/',
                          'src="https://%s/media/django-summernote/' % settings.MAIN_HOST,
                          self.content)
        except:
            return self.content

    # def get_likes_display(self):
    # 	return self.likes.all().count()
    # get_likes_display.short_description = '좋아요'
    # get_likes_display.admin_order_field = 'likes__count'


class Comment(models.Model):
    """
    코멘트 모델
    """
    writing = models.ForeignKey(Writing, verbose_name='게시글', related_name='comments', db_index=True,
                                on_delete=models.CASCADE)
    content = models.TextField('내용', blank=True)
    created_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='작성자', null=True, blank=True,
                                     related_name='board_comments', on_delete=models.SET_NULL)
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    updated_datetime = models.DateTimeField('수정일시', null=True, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '코멘트'
        ordering = ('id',)

    def __str__(self):
        return self.content[:20] + ('...' if len(self.content) > 20 else '')

    def save(self, *args, **kwargs):
        if 'comment' in BOARD_FUNCTIONS[self.writing.board]:
            return super(Comment, self).save()
        raise ValueError('코멘트를 사용할 수 없는 게시판입니다.')


class Answer(Comment):
    """
    답변 프록시 모델
    """
    class Meta:
        verbose_name = verbose_name_plural = '답변'
        proxy = True

    def save(self, *args, **kwargs):
        if 'answer' in BOARD_FUNCTIONS[self.writing.board]:
            return super(Comment, self).save()
        raise ValueError('답변을 사용할 수 없는 게시판입니다.')


class AttachFile(models.Model):
    """
    게시판 첨부파일 모델
    """
    writing = models.ForeignKey(Writing, verbose_name='게시글', related_name='files', on_delete=models.CASCADE)
    attach = models.FileField('첨부파일')
    is_active = models.BooleanField('유효성', default=True)

    class Meta:
        verbose_name = verbose_name_plural = '첨부파일'

    def __str__(self):
        return str(self.attach)

    def save(self, *args, **kwargs):
        if 'attach' in BOARD_FUNCTIONS[self.writing.board]:
            return super(AttachFile, self).save()
        raise ValueError('첨부파일을 사용할 수 없는 게시판입니다.')

    def handle_attach(self, file_obj):
        file = UploadFileHandler(self, file_obj).with_parent('writing_id').with_timestamp()
        return file.save(to='attach')

    def filename_display(self):
        return self.attach.name.split('/')[-1]


class TitleImage(AttachFile):
    """
    대표 이미지 프록시 모델
    """
    class Meta:
        verbose_name = verbose_name_plural = '대표 이미지'
        proxy = True

    def save(self, *args, **kwargs):
        if 'title_image' in BOARD_FUNCTIONS[self.writing.board]:
            return super(AttachFile, self).save()
        raise ValueError('대표 이미지를 사용할 수 없는 게시판입니다.')


class ViewLocation(models.Model):
    """
    게시판 노출 위치 모델
    """
    LOCATIONS = (
        ('customer', '고객'),
        ('helper', '헬퍼'),
    )

    writing = models.OneToOneField(Writing, verbose_name='게시글', related_name='location', on_delete=models.CASCADE)
    location = models.CharField('노출 위치', choices=LOCATIONS, db_index=True, max_length=10)

    class Meta:
        verbose_name = verbose_name_plural = '노출위치'

    def __str__(self):
        return dict(self.LOCATIONS)[self.location]

    def save(self, *args, **kwargs):
        if 'location' in BOARD_FUNCTIONS[self.writing.board]:
            return super(ViewLocation, self).save()
        raise ValueError('노출위치를 사용할 수 없는 게시판입니다.')


class ViewTerm(models.Model):
    """
    게시판 노출기간 모델
    """
    writing = models.OneToOneField(Writing, verbose_name='게시글', related_name='term', on_delete=models.CASCADE)
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일')

    class Meta:
        verbose_name = verbose_name_plural = '노출기간'

    def __str__(self):
        return '%s ~ %s' % (self.start_date, self.end_date)

    def save(self, *args, **kwargs):
        if 'term' in BOARD_FUNCTIONS[self.writing.board]:
            return super(ViewTerm, self).save()
        raise ValueError('노출기간을 사용할 수 없는 게시판입니다.')


class WritingProxyManager(models.Manager):
    """
    게시글 프록시 쿼리셋
    """
    def get_queryset(self):
        qs = super(WritingProxyManager, self).get_queryset()
        board = self.model._meta.model_name.replace('writing', '')
        if board:
            qs = qs.filter(board=BOARD_IDS[board])
        return qs


class ContactWriting(Writing):
    """
    1:1 문의 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '1:1 문의'
        verbose_name_plural = '1:1 문의'
        proxy = True


class PartnershipWriting(Writing):
    """
    제휴/제안 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '제휴/제안'
        verbose_name_plural = '제휴/제안'
        proxy = True


class NoticeWriting(Writing):
    """
    공지 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '공지'
        verbose_name_plural = '공지'
        proxy = True


class EventWriting(Writing):
    """
    이벤트 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '이벤트'
        verbose_name_plural = '이벤트'
        proxy = True


class MagazineWriting(Writing):
    """
    매거진 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '매거진'
        verbose_name_plural = '매거진'
        proxy = True


class WebtoonWriting(Writing):
    """
    웹툰 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '웹툰'
        verbose_name_plural = '웹툰'
        proxy = True


class FAQWriting(Writing):
    """
    FAQ 글 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQ'
        proxy = True


class ArticleWriting(Writing):
    """
    홈페이지 - 보도자료 모델
    """
    objects = WritingProxyManager()

    class Meta:
        verbose_name = '보도자료'
        verbose_name_plural = '보도자료'
        proxy = True


# class Like(models.Model):
# 	"""
# 	좋아요(추천) 모델
# 	"""
# 	writing = models.ForeignKey(Writing, verbose_name='게시글', related_name='likes', on_delete=models.CASCADE)
# 	user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='좋아한 사용자', related_name='likes', on_delete=models.CASCADE)
# 	liked_datetime = models.DateTimeField('조회일시', auto_now=True)
#
# 	class Meta:
# 		verbose_name = verbose_name_plural = '좋아요'
#
# 	def __str__(self):
# 		return '[Like] %s' % self.writing
#
# 	def save(self, *args, **kwargs):
# 		if not self.writing.board.allow_like:
# 			raise PermissionDenied
# 		return super(Like, self).save(*args, **kwargs)
#
#

#
# class Permission(models.Model):
# 	"""
# 	권한 모델
# 	"""
# 	PERM_TYPES = (
# 		# 글
# 		('w_list', '목록 보기'),
# 		('w_read_own', '자신의 글 읽기'),
# 		('w_read', '글 읽기'),
# 		('w_write', '글 작성'),
# 		('w_notice', '공지 글 설정'),
# 		('w_edit_own', '자신의 글 수정'),
# 		('w_edit', '글 수정'),
# 		('w_delete_own', '자신의 글 삭제'),
# 		('w_delete', '글 삭제'),
# 		# ('w_like', '좋아요'),
# 		('w_view_hits', '조회수 보기'),
# 		# 답글
# 		# ('r_read_own', '자신의 글에 대한 답글 읽기'),
# 		# ('r_read', '답글 읽기'),
# 		# ('r_write', '답글 작성'),
# 		# ('r_edit_own', '자신의 답글 수정'),
# 		# ('r_edit', '답글 수정'),
# 		# ('r_delete_own', '자신의 답글 삭제'),
# 		# ('r_delete', '답글 삭제'),
# 		# 코멘트
# 		('c_write', '코멘트 작성'),
# 		('c_edit_own', '자신의 코멘트 수정'),
# 		('c_edit', '코멘트 수정'),
# 		('c_delete_own', '자신의 코멘트 삭제'),
# 		('c_delete', '코멘트 삭제'),
# 		# 첨부파일
# 		('f_up', '첨부파일 업로드'),
# 		('f_down', '첨부파일 다운로드'),
# 	)
# 	board = models.ForeignKey(Board, verbose_name='게시판', related_name='perms', on_delete=models.CASCADE)
# 	group = models.ForeignKey(Group, verbose_name='그룹', related_name='board_perms', null=True, blank=True, on_delete=models.CASCADE)
# 	perms = ArrayField(models.CharField(max_length=20, choices=PERM_TYPES), verbose_name='권한', blank=True, default=list)
#
# 	class Meta:
# 		verbose_name = verbose_name_plural = '권한'
# 		# unique_together = ('board', 'group')
#
# 	def __str__(self):
# 		return 'Permission : %s - %s' % (self.board, self.group)
