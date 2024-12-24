import hashlib
import logging

import requests

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.formats import localize
from django.contrib.postgres.fields import ArrayField, JSONField
from django.forms import ValidationError

from .utils import PaymentAPI, BillingAPI
from common.utils import add_comma
from accounts.models import Helper, BankAccount
from missions.models import Bid


logger = logging.getLogger('payment')


"""
querysets
"""


class OptionalBalanceQuerySet(models.QuerySet):
    """
    잔액 표시 쿼리셋
    """
    def get_balance(self):
        last = self.order_by('id').last()
        if last:
            return last.balance
        return 0


class WithdrawQuerySet(models.QuerySet):
    """
    인출신청 쿼리셋
    """
    def requested_amount(self):
        return sum(self.filter(
            failed_datetime__isnull=True,
            done_datetime__isnull=True
        ).values_list('amount', flat=True))

    def requested_set(self):
        return self.filter(done_datetime__isnull=True, failed_datetime__isnull=True)


class PointVoucherQuerySet(models.QuerySet):
    """
    포인트 상품권 쿼리셋
    """
    def usable_set(self):
        return self.filter(used_datetime__isnull=True, expire_date__gte=timezone.now().date())

    def get_usable(self, code, user):
        try:
            obj = self.usable_set().get(code=code, user=user)
        except:
            try:
                obj = PointVoucherTemplate.objects.get(code=code, is_repetitive_use=True, is_active=True)
            except:
                return None
        return obj if obj.check_usable(user) else False


class CouponQuerySet(models.QuerySet):
    """
    쿠폰 쿼리셋
    """
    def usable_set(self):
        return self.filter(used_datetime__isnull=True, expire_date__gte=timezone.now().date())

    def get_usable(self, user, bid=None):
        qs = self.usable_set().filter(user=user)
        if bid:
            usable_ids = []
            for c in qs:
                if c.calculate_discount(bid):
                    usable_ids.append(c.id)
            qs = qs.filter(id__in=usable_ids)
        return qs

    def register(self, code, user):
        code = code.upper()
        try:
            template = CouponTemplate.objects.get(user_register_code=code, is_active=True)
        except:
            return None
        if Coupon.objects.filter(template=template, user=user).exists():
            return False
        return self.create_from_template(template, [user], user)

    def create_from_template(self, template, users, issued_user=None, tasker=None):
        return template.issue(users, issued_user, tasker)


class RewardQuerySet(models.QuerySet):
    """
    리워드 쿼리셋
    """
    def get_active(self, reward_type):
        now = timezone.now().date()
        date_appointed = self.filter(reward_type=reward_type, start_date__lte=now, end_date__gte=now)
        if date_appointed.exists():
            return date_appointed.order_by('id').last()
        return self.filter(reward_type=reward_type, end_date__isnull=True).order_by('id').last()


class PaymentQuerySet(models.QuerySet):
    """
    결제 쿼리셋
    """
    def get_succeeded(self):
        return self.filter(is_succeeded=True)

    def get_paid(self):
        return self.get_succeeded().exclude(pay_method='Refund').exclude(result__has_key='canceled')

    def get_refunded(self):
        return self.get_succeeded().filter(pay_method='Refund')

    def get_coupon_used(self):
        return self.filter(coupon__used_datetime__isnull=False)

    def get_paid_amount(self, exclude_points=False):
        """카드 및 포인트 결제금액합"""
        paid = list(zip(*self.get_paid().values_list('amount', 'point__amount')))
        if not paid:
            return 0
        amount = sum(paid[0])
        if not exclude_points and len(paid) > 1:
            amount -= sum([p for p in paid[1] if p])
        return amount

    def get_discounted_amount(self):
        discounted = sum([p.coupon.calculate_discount(p.bid) for p in self.get_coupon_used()])
        return discounted


"""
models
"""


class Point(models.Model):
    """
    포인트 내역 모델
    """
    ADDED_TYPES = (
        (0, '시스템'),
        (1, '계정간 이전'),
        (5, '고객 보상'),
        (9, '임직원 포인트 충전'),
        (11, '비대면바우처 충전 (+부가세)'),
        (12, '비대면바우처 충전 (부가세 충전 제외)'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='회원', related_name='points',
                             on_delete=models.CASCADE)
    amount = models.IntegerField('금액')
    balance = models.IntegerField('잔액', blank=True)
    created_datetime = models.DateTimeField('일시', auto_now_add=True)
    _detail = models.CharField('내역 보존', max_length=100, blank=True, default='')
    memo = models.TextField('메모', blank=True, default='')
    added_type = models.PositiveSmallIntegerField('추가유형', choices=ADDED_TYPES, blank=True, default=0)

    objects = OptionalBalanceQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '포인트 내역'
        ordering = ('id',)

    def __str__(self):
        return str(self.amount)

    @property
    def detail(self):
        if hasattr(self, 'review'):
            return '[리뷰작성] %s' % self.review.bid._mission.code
        if hasattr(self, 'bid'):
            if self.amount < 0:
                return '[포인트 차감] %s' % self.bid._mission.code
            else:
                return '[미션완료 리워드] %s' % self.bid._mission.code
        if hasattr(self, 'voucher'):
            return '[포인트 상품권 사용] %s' % self.voucher.template.name
        if hasattr(self, 'payment'):
            if self.amount > 0:
                return '[결제 포인트차감 복구] %s' % self.payment.bid._mission.code
            else:
                return '[결제 포인트차감] %s' % self.payment.bid._mission.code
        if self.amount > 0:
            return '[포인트 지급]'
        if self._detail:
            return '[미션완료 리워드 환수] %s' % str(self._detail)
        else:
            return '[포인트 차감]'

    @property
    def detail_memo(self):
        return self.detail + ' ' + self.memo

    def save_detail(self):
        self._detail = self.detail
        self.save()


class PointVoucherTemplate(models.Model):
    """
    포인트 상품권 템플릿 모델
    """
    name = models.CharField('포인트 상품권명', max_length=50)
    description = models.CharField('포인트 상품권 설명', max_length=200, blank=True)
    price = models.IntegerField('포인트')
    code = models.CharField('템플릿 코드', unique=True, max_length=6,
                            help_text='반복사용 상품권의 경우 여기에 입력한 코드를 그대로 사용하며, 반복사용이 아닌 경우에는 코드 뒤에 일련번호가 붙는 형태로 발급됩니다.')
    is_repetitive_use = models.BooleanField('반복사용 상품권', blank=True, default=True)
    is_new_users_only = models.BooleanField('신규 회원만 이용가능', blank=True, default=False)
    active_days = models.PositiveSmallIntegerField('유효기간일수', default=30)
    is_active = models.BooleanField('활성화', blank=True, default=True)

    class Meta:
        verbose_name = verbose_name_plural = '포인트 상품권 템플릿'

    def __str__(self):
        return self.name

    def check_usable(self, user):
        if self.is_new_users_only and user.mission_done_count > 0:
            return False
        return bool(self.is_repetitive_use and self.is_active)

    def use(self, user):
        # todo: 같은 템플릿으로 한 사람에게 여러번 발급하는 경우에 대한 고려 필요
        voucher, is_created = self.vouchers.get_or_create(user=user)
        if is_created:
            return voucher.use()
        return None


class PointVoucher(models.Model):
    """
    포인트 상품권 모델
    """
    template = models.ForeignKey(PointVoucherTemplate, verbose_name='포인트 상품권', related_name='vouchers', on_delete=models.PROTECT)
    code = models.CharField('포인트 상품권 코드', max_length=16, blank=True, default='')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='발급 받은 회원', null=True, blank=True,
                             related_name='vouchers', on_delete=models.CASCADE)
    point = models.OneToOneField(Point, verbose_name='포인트 충전', null=True, blank=True,
                                 related_name='voucher', on_delete=models.PROTECT)
    expire_date = models.DateField('유효기한')
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    used_datetime = models.DateTimeField('사용일시', null=True)

    objects = PointVoucherQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '발급된 포인트 상품권'

    def __str__(self):
        return '%s [~%s]' % (self.template.name, self.expire_date)

    def use(self, user=None):
        if self.template.is_new_users_only and self.user.mission_done_count > 0:
            return False
        self.point = Point.objects.create(user=self.user, amount=self.template.price)
        self.used_datetime = timezone.now()
        self.save()
        return self

    @property
    def is_expired(self):
        return bool(self.expire_date < timezone.now().date())

    def check_usable(self, user):
        if self.template.is_new_users_only and user.mission_done_count > 0:
            return False
        return not bool(self.is_expired or self.used_datetime)


class CouponTemplate(models.Model):
    """
    쿠폰 템플릿 모델
    """
    name = models.CharField('쿠폰명', max_length=50)
    description = models.CharField('쿠폰 설명', max_length=200, blank=True)
    price = models.PositiveIntegerField('가액', help_text='100이하로 지정하는 경우 할인율(%)로 적용됩니다.')
    amount_condition = models.PositiveIntegerField('금액 제한조건', blank=True, default=0,
                                                   help_text='정액 쿠폰일 경우 사용가능 미션 최저금액, 정률 쿠폰일 경우 할인 최대금액')
    user_register_code = models.CharField('유져 등록 코드', blank=True, default='', max_length=6,
                                          help_text='유져가 직접 등록할 쿠폰인 경우에만 값을 입력해주세요.')
    active_days = models.PositiveSmallIntegerField('유효기간일수', default=30)
    is_active = models.BooleanField('활성화', blank=True, default=True)

    class Meta:
        verbose_name = verbose_name_plural = '쿠폰 템플릿'

    def __str__(self):
        return '%s %s [%s / %s / 유효기간 %s일]' % (self.user_register_code, self.name, self.discount, self.condition, self.active_days)

    def clean(self):
        if self.user_register_code:
            self.user_register_code = self.user_register_code.upper()
            if CouponTemplate.objects.filter(user_register_code=self.user_register_code).exclude(id=self.id).exists():
                raise ValidationError({'user_register_code': '중복된 코드입니다.'})
        return super(CouponTemplate, self).clean()

    @property
    def discount(self):
        if self.price > 100:
            return add_comma(self.price) + '원'
        return '%s%%' % self.price

    @property
    def condition(self):
        if self.price > 100:
            return '%s원 이상 결제시 사용가능' % add_comma(self.amount_condition)
        return '최대 %s원 할인' % add_comma(self.amount_condition)

    def issue(self, users, issued_user=None, tasker=None):
        if not self.is_active:
            return False
        coupons = []
        for user in users:
            coupons.append(self.coupons.create(user=user, issued_user=issued_user, tasker=tasker))
        return coupons


class Coupon(models.Model):
    """
    쿠폰 모델
    """
    template = models.ForeignKey(CouponTemplate, verbose_name='쿠폰', related_name='coupons', on_delete=models.PROTECT)
    expire_date = models.DateField('유효기한', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='발급받은 회원', related_name='coupons',
                             on_delete=models.CASCADE)
    issued_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='발급한 회원', related_name='issued_coupons',
                             on_delete=models.CASCADE, null=True, blank=True)
    tasker = models.ForeignKey('notification.Tasker', verbose_name='태스커', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='coupons')
    created_datetime = models.DateTimeField('발급일시', auto_now_add=True)
    used_datetime = models.DateTimeField('사용일시', null=True, blank=True)

    objects = CouponQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '쿠폰'

    def __str__(self):
        return '%s %s [~%s]' % (self.template.name, self.code, self.expire_date)

    def save(self, *args, **kwargs):
        if not self.expire_date:
            self.expire_date = self.calculate_expire_date()
        return super(Coupon, self).save(*args, **kwargs)

    @property
    def name(self):
        return self.template.name

    @property
    def discount(self):
        return self.template.discount

    @property
    def condition(self):
        return self.template.condition

    @property
    def code(self):
        return '%sU%s%s' % (self.template.user_register_code or self.template.id, self.user.code, self.id)

    @property
    def is_expired(self):
        return bool(self.expire_date < timezone.now().date())

    @property
    def is_usable(self):
        return bool(not self.is_expired and not self.used_datetime)

    def calculate_expire_date(self):
        now = self.created_datetime or timezone.now().date()
        return now + timezone.timedelta(days=self.template.active_days)

    def calculate_discount(self, bid):
        if self.template.price > 100:
            return self.template.price if bid.amount >= self.template.amount_condition else 0
        else:
            return min(int(bid.amount * self.template.price / 100), self.template.amount_condition)

    def use(self):
        self.used_datetime = timezone.now()
        self.save()

    def unuse(self):
        self.used_datetime = None
        self.save()


class Cash(models.Model):
    """
    캐쉬 내역 모델
    """
    helper = models.ForeignKey(Helper, verbose_name='회원', related_name='cashes', on_delete=models.CASCADE)
    amount = models.IntegerField('금액')
    balance = models.IntegerField('잔액', blank=True)
    created_datetime = models.DateTimeField('일시', auto_now_add=True)
    _detail = models.CharField('내역 보존', max_length=100, blank=True, default='')
    memo = models.TextField('메모', blank=True, default='')

    objects = OptionalBalanceQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '캐쉬 내역'

    def __str__(self):
        return str(self.amount)

    @property
    def detail(self):
        if hasattr(self, 'review'):
            return '[리뷰작성] %s' % self.review.bid._mission.code
        if hasattr(self, 'bid'):
            if self.amount > 0:
                return '[미션수행비] %s' % self.bid._mission.code
        if hasattr(self, 'withdraw'):
            return '[인출] %s' % str(self.withdraw.done_datetime)
        try:
            object_id = int(self._detail)
        except:
            object_id = None
        if object_id:
            return '[미션수행비 취소] %s' % str(self._detail)
        if self.amount > 0:
            return '[캐쉬 지급]'
        if self._detail:
            return '[미션수행비 환수] %s' % str(self._detail)
        else:
            return '[캐쉬 차감]'

    @property
    def detail_memo(self):
        return self.detail + ' ' + self.memo

    def save_detail(self):
        self._detail = self.detail
        self.save()


class Withdraw(models.Model):
    """
    인출요청 모델
    """
    STATUS = (
        ('requested', '요청됨'),
        ('done', '인출완료'),
        ('failed', '인출실패'),
    )

    helper = models.ForeignKey(Helper, verbose_name='헬퍼', related_name='withdraws', on_delete=models.CASCADE)
    amount = models.IntegerField('금액', default=0)
    cash = models.OneToOneField(Cash, verbose_name='캐쉬', null=True, blank=True, related_name='withdraw',
                                on_delete=models.PROTECT)
    bank_account = models.ForeignKey(BankAccount, verbose_name='은행 계좌', null=True, blank=True,
                                     related_name='withdraws', on_delete=models.CASCADE)
    requested_datetime = models.DateTimeField('요청일시', auto_now_add=True)
    failed_datetime = models.DateTimeField('실패일시', null=True, blank=True)
    done_datetime = models.DateTimeField('처리일시', null=True, blank=True)

    objects = WithdrawQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '인출요청'

    def __str__(self):
        return str(self.amount)

    def save(self, *args, **kwargs):
        if not self.bank_account:
            self.bank_account = self.helper.bank_account
        return super(Withdraw, self).save(*args, **kwargs)

    def finish(self):
        self.cash = Cash.objects.create(helper=self.helper, amount=-self.amount)
        self.done_datetime = timezone.now()
        self.save()
        return self

    def fail(self):
        self.failed_datetime = timezone.now()
        self.save()
        return self

    @property
    def state(self):
        if self.done_datetime:
            return 'done'
        if self.failed_datetime:
            return 'failed'
        return 'requested'

    @property
    def state_text(self):
        return dict(self.STATUS)[self.state]

    @property
    def handled_datetime(self):
        handled = {
            'done': self.done_datetime,
            'failed': self.failed_datetime,
            'requested': ''
        }
        return handled[self.state]

    def get_state_display(self):
        return '[%s] %s' % (self.state_text, localize(self.handled_datetime))
    get_state_display.short_description = '처리 상태'


class Billing(models.Model):
    """
    빌링 모델
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='회원', related_name='billings',
                             on_delete=models.CASCADE)
    billkey = models.CharField('빌키', max_length=20, blank=True, default='')
    ref_no = models.CharField('거래번호', max_length=20, blank=True, default='')
    card_company_no = models.CharField('카드사코드', max_length=2, blank=True, default='')
    card_name = models.CharField('카드명', max_length=20, blank=True, default='')
    card_no = models.CharField('카드번호', max_length=20, blank=True, default='')
    customer_name = models.CharField('고객명', max_length=16, blank=True, default='')
    customer_tel_no = models.CharField('고객 연락처', max_length=13, blank=True, default='')
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    canceled_datetime = models.DateTimeField('해지일시', blank=True, null=True, default=None)

    class Meta:
        verbose_name = verbose_name_plural = '빌링'

    def __str__(self):
        return self.card_name + ' ' + self.card_no[:4] + ('(해지)' if self.canceled_datetime else '')

    @property
    def mbrRefNo(self):
        return 'U' + self.user.code + str(self.id)


class Payment(models.Model):
    """
    결제 모델
    """
    PAY_METHODS = (
        ('POINT', '전액 포인트'),
        ('CARD', '신용카드'),
        ('Card', '신용카드 (이니시스)'),
        ('Refund', '결제취소')
    )
    bid = models.ForeignKey(Bid, verbose_name='입찰', related_name='payment', on_delete=models.CASCADE)
    billing = models.ForeignKey(Billing, verbose_name='빌링', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='paid')
    point = models.OneToOneField(Point, verbose_name='포인트 사용', null=True, blank=True,
                                 related_name='payment', on_delete=models.PROTECT)
    coupon = models.ForeignKey(Coupon, verbose_name='쿠폰 사용', null=True, blank=True,
                               related_name='payment', on_delete=models.PROTECT)
    pay_method = models.CharField('결제방법', choices=PAY_METHODS, max_length=10, blank=True, default='Card')
    amount = models.IntegerField('금액', default=0)
    result = JSONField('결제결과', default=dict)
    payment_id = models.CharField('결제모듈 고유 ID', max_length=40, blank=True, default='')
    authenticated_no = models.CharField('승인번호', max_length=40, blank=True, default='')
    authenticated_datetime = models.DateTimeField('승인일시', null=True)
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)
    is_succeeded = models.BooleanField('성공여부', blank=True, default=True)

    objects = PaymentQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '결제'

    def __str__(self):
        return '[%s] %s' % (dict(self.PAY_METHODS)[self.pay_method], self.bid.mission.code)

    def save(self, *args, **kwargs):
        if self.authenticated_no:
            self.authenticated_no = ''.join(filter(str.isdigit, self.authenticated_no))
        return super(Payment, self).save(*args, **kwargs)

    @property
    def summary(self):
        rtn = '[%s%s] %s' % (
            '간편' if self.billing_id else '',
            self.get_pay_method_display(),
            add_comma(self.amount)
        )
        if self.point:
            rtn += ' (포인트 %s)' % add_comma(-self.point.amount)
        if self.coupon:
            rtn += ' (%s %s)' % (self.coupon.name, add_comma(self.coupon.calculate_discount(self.bid)))
        return rtn

    @property
    def can_cancel(self):
        return self.pay_method != 'Refund' and self.is_succeeded and 'canceled' not in self.result

    def use_point(self, point_amount, restrict=True):
        if restrict and self.bid.mission.user.points.get_balance() < point_amount:
            return False
        self.point = Point.objects.create(user=self.bid.mission.user, amount=-point_amount)
        self.save()
        return True

    def cancel(self):
        """결제 취소"""
        if not self.can_cancel:
            logger.error('[결제취소 오류] 취소할 수 없는 결제 상태')
            return False

        # 취소 데이터
        canceled_payment = {
            'bid_id': self.bid_id,
            'pay_method': 'Refund',
            'amount': -self.amount,
        }

        # 카드 취소
        if self.amount > 0:
            if self.pay_method == 'Card':
                canceled_payment = self.cancel_Card(canceled_payment)
            if self.pay_method == 'CARD':
                canceled_payment = self.cancel_CARD(canceled_payment)

        # 취소 오브젝트 생성 후, 카드 취소에 실패한 경우 중단
        canceled = self._meta.model.objects.create(**canceled_payment)
        if not canceled.is_succeeded:
            logger.error('[결제취소 오류] 카드취소 실패')
            logger.error(canceled_payment)
            return False

        # 포인트 취소
        if self.point:
            canceled.use_point(self.point.amount, restrict=False)

        # 쿠폰 사용 취소
        if self.coupon:
            self.coupon.unuse()

        # 원래 객체에 취소 정보 저장
        self.result['canceled'] = canceled.id
        self.save()

        return True

    def cancel_Card(self, canceled_payment):
        if not self.payment_id:
            logger.error('[결제취소 오류] 결제모듈 고유 ID가 없음')
            return False
        canceled_payment.update({
            'authenticated_no': self.authenticated_no,
        })
        payload = {
            'type': 'Refund',
            'paymethod': 'Card',
            'timestamp': timezone.now().strftime('%Y%m%d%H%M%S'),
            'clientIp': settings.SERVER_IP,
            'mid': settings.PAYMENT_INI_MID,
            'tid': self.result['P_TID'] or self.payment_id,
            'msg': 'cancel',
        }
        payload.update({
            'hashData': hashlib.sha512(str(
                settings.PAYMENT_INI_KEY
                + payload['type']
                + payload['paymethod']
                + payload['timestamp']
                + payload['clientIp']
                + payload['mid']
                + payload['tid']
            ).encode('utf-8')).hexdigest()
        })
        headers = {'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'}
        response = requests.post(settings.PAYMENT_REFUND_URL, data=payload, headers=headers)
        result = response.json()
        if 300 > response.status_code >= 200:
            canceled_payment.update({'result': result})
            if 'resultCode' not in canceled_payment['result'] or canceled_payment['result']['resultCode'] != '00':
                canceled_payment.update({'is_succeeded': False})
                logger.error('[결제취소 오류] 취소요청 내용 : %s' % payload)
        else:
            canceled_payment.update({'is_succeeded': False})
        logger.error('[결제취소] 요청 결과 : %s' % result)

        return canceled_payment

    def cancel_CARD(self, canceled_payment):
        if not self.payment_id:
            logger.error('[결제취소 오류] 결제모듈 고유 ID가 없음')
            return False

        if self.billing_id:
            pay = BillingAPI()
        else:
            pay = PaymentAPI()
        cancel_result = pay.request_cancel(self)
        if cancel_result:
            _, canceled_payment['result'] = cancel_result
        else:
            canceled_payment['is_succeeded'] = False

        return canceled_payment


class Reward(models.Model):
    """
    리워드 모델
    """
    REWARD_TYPES = (
        ('helper_created_review', '[헬퍼] 리뷰작성'),
        ('customer_created_review', '[고객] 리뷰작성'),
        ('customer_finished_mission', '[고객] 미션완료'),
        ('customer_joined_by_recommend', '[고객] 가입시 추천인 입력'),
        ('helper_recommend_done_first', '[헬퍼] 추천에 의해 가입한 회원이 첫 미션완료'),
        ('customer_recommend_done_first', '[고객] 추천에 의해 가입한 회원이 첫 미션완료'),
        ('helper_recommend_done', '[헬퍼] 추천에 의해 가입한 회원이 미션완료'),
        ('customer_recommend_done', '[고객] 추천에 의해 가입한 회원이 미션완료'),
    )

    reward_type = models.CharField('리워드 종류', max_length=30, choices=REWARD_TYPES)
    amount_or_rate = models.PositiveSmallIntegerField('금액 또는 비율', help_text='100 미만으로 입력시 비율(%)로 계산합니다.')
    start_date = models.DateField('시작일', null=True, blank=True)
    end_date = models.DateField('종료일', null=True, blank=True)
    created_datetime = models.DateTimeField('작성일시', auto_now_add=True)

    objects = RewardQuerySet.as_manager()

    class Meta:
        verbose_name = verbose_name_plural = '리워드'

    def __str__(self):
        return '%s : %s' % (self.get_reward_type_display(), self.get_amount_or_rate_display())

    def save(self, *args, **kwargs):
        if bool(self.start_date) is  not bool(self.end_date):
            raise ValueError('시작일과 종료일은 하나만 지정할 수 없습니다.')
        return super(Reward, self).save(*args, **kwargs)

    def calculate_reward(self, base_amount):
        if self.amount_or_rate >= 100:
            return self.amount_or_rate
        if 0 < self.amount_or_rate < 100:
            return int(base_amount * self.amount_or_rate / 100)
        return 0

    def get_amount_or_rate_display(self):
        if self.amount_or_rate < 100:
            return '%s%%' % self.amount_or_rate
        else:
            return '₩%s' % add_comma(self.amount_or_rate)
    get_amount_or_rate_display.short_description = '금액 또는 비율'
    get_amount_or_rate_display.admin_order_field = 'amount_or_rate'
