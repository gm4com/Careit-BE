from django.utils import timezone

from rest_framework import serializers
from accounts import models

from common.fields import FullURLField
from common.utils import CachedProperties
from common.exceptions import Errors
from accounts.serializers import (
    ProfileCodeSerializer, ProfilePhotoSerializer,
    AdminProfileSerializer, HelperReadOnlySerializer, MissionProfileSerializer
)
from accounts.models import Helper
from base.models import BannedWord
from notification.models import Notification
from notification.serializers import NotificationResultSerializer
from .models import (
    MissionTemplate, MissionType, Address, MultiMission, MultiAreaMission, Mission, MissionFile, Bid, BidFile, Interaction,
    Review, Report, TemplateCategory, TemplateTag, TemplateQuestion, UserBlock, FavoriteUser
)


class MissionTypeSerializer(serializers.ModelSerializer):
    """
    미션타입 시리얼라이져
    """
    class Meta:
        model = MissionType
        fields = ('id', 'title', 'description', 'code', 'class_name', 'minimum_amount', 'charge_rate', 'bidding_limit')


class AddressSerializer(serializers.ModelSerializer):
    """
    주소 시리얼라이져
    """
    class Meta:
        model = Address
        fields = ('id', 'name', 'area', 'detail_1', 'detail_2', 'readable')
        order_by = ('missions_mission_stopovers__id',)

    def create(self, validated_data):
        validated_data.update({'user': self.context['request'].user})
        return super(AddressSerializer, self).create(validated_data)


class MultiAreaMissionSerializer(serializers.ModelSerializer):
    """
    다중지역 미션 시리얼라이져
    """
    user = MissionProfileSerializer(required=False, read_only=True)
    final_address = serializers.DictField(read_only=True, required=False)
    state = serializers.CharField(read_only=True)
    charge_rate = serializers.IntegerField(read_only=True)
    warnings = serializers.ListField(read_only=True)
    customer_paid = serializers.IntegerField(read_only=True, required=False)
    customer_point_used = serializers.IntegerField(read_only=True, required=False)
    bid_canceled_datetime = serializers.DateTimeField(read_only=True, required=False)
    bid_done_datetime = serializers.DateTimeField(read_only=True, required=False)
    mission_type = serializers.IntegerField(source='mission_type_id', read_only=True)
    title = serializers.CharField(read_only=True)
    banner = serializers.ImageField(read_only=True)
    requested_datetime = serializers.DateTimeField(read_only=True)
    active_due = serializers.DateTimeField(read_only=True)
    content = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MultiAreaMission
        fields = ('id', 'code', 'user', 'mission_type', 'title', 'banner', 'summary', 'content', 'customer_mobile',
                  'final_address', 'amount', 'charge_rate', 'state', 'warnings', 'requested_datetime',
                  'customer_paid', 'customer_point_used', 'bid_canceled_datetime', 'bid_done_datetime', 'active_due')

    def get_content(self, instance):
        return instance.parsed_content


class MultiMissionChildSerializer(serializers.ModelSerializer):
    """
    다중지역 미션 시리얼라이져 (child용)
    """
    final_address = serializers.DictField(read_only=True, required=False)
    state = serializers.CharField(read_only=True)
    helper = HelperReadOnlySerializer(read_only=True, required=False)

    class Meta:
        model = MultiAreaMission
        fields = ('id', 'final_address', 'amount', 'customer_mobile', 'state', 'helper', 'active_bid_id')
        extra_kwargs = {
            'active_bid_id': {'read_only': True}
        }


class MultiMissionSerializer(serializers.ModelSerializer):
    """
    다중 미션 시리얼라이져
    """
    user = AdminProfileSerializer(required=False, read_only=True)
    children = MultiMissionChildSerializer(many=True, read_only=True, required=False)
    content = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = MultiMission
        fields = ('id', 'code', 'user', 'mission_type', 'title', 'banner', 'summary', 'content',
                  'requested_datetime', 'children')
        extra_kwargs = {
            'id': {'read_only': True},
        }

    def get_content(self, instance):
        return instance.parsed_content


class MissionFileSerializer(serializers.ModelSerializer):
    """
    미션 수행 관련 파일 시리얼라이져
    """
    class Meta:
        model = MissionFile
        fields = ('id', 'attach')


class MissionSerializer(serializers.ModelSerializer):
    """
    미션 시리얼라이져
    """
    user = MissionProfileSerializer(required=False, read_only=True)
    is_web = serializers.BooleanField(required=False, read_only=True)
    stopovers = AddressSerializer(many=True, required=False, write_only=True)
    final_address = AddressSerializer(write_only=True, required=False)
    state = serializers.CharField(read_only=True)
    charge_rate = serializers.IntegerField(read_only=True)
    active_due = serializers.DateTimeField(read_only=True)
    warnings = serializers.ListField(read_only=True)
    assigned_helper = serializers.CharField(write_only=True, required=False)
    assigned_bid_ids = serializers.ListField(read_only=True, required=False)
    bidded_count = serializers.IntegerField(read_only=True, required=False)
    bidded_lowest = serializers.IntegerField(read_only=True, required=False)
    customer_coupon_used = serializers.IntegerField(read_only=True, required=False)
    customer_paid = serializers.IntegerField(read_only=True, required=False)
    customer_point_used = serializers.IntegerField(read_only=True, required=False)
    bid_canceled_datetime = serializers.DateTimeField(read_only=True, required=False)
    bid_done_datetime = serializers.DateTimeField(read_only=True, required=False)
    files = MissionFileSerializer(read_only=True, many=True, required=False)
    push_result = NotificationResultSerializer(read_only=True, required=False)

    class Meta:
        model = Mission
        fields = (
            'id', 'code', 'user', 'is_web', 'mission_type', 'content', 'due_datetime', 'is_due_date_modifiable',
            'is_due_time_modifiable', 'stopovers', 'final_address', 'request_areas', 'product', 'budget',
            'amount_high', 'amount_low', 'charge_rate', 'bid_limit_datetime', 'active_due', 'state', 'files',
            'assigned_helper', 'warnings', 'requested_datetime', 'assigned_bid_ids', 'bidded_count', 'bidded_lowest',
            'customer_coupon_used', 'customer_paid', 'customer_point_used', 'bid_canceled_datetime', 'bid_done_datetime', 'push_result'
        )
        extra_kwargs = {
            'requested_datetime': {'read_only': True},
            'due_datetime': {'write_only': True},
            'bid_limit_datetime': {'read_only': True}
        }

    def create(self, validated_data):
        final_address = validated_data.pop('final_address', None)
        stopovers = validated_data.pop('stopovers', [])
        request_areas = validated_data.pop('request_areas', [])
        assigned_helper = validated_data.pop('assigned_helper', '')
        user = validated_data.pop('user', self.context['request'].user)

        helper_obj = None
        if assigned_helper:
            helper_obj = Helper.objects.filter(user__code=assigned_helper).last()
            if not helper_obj:
                raise Errors.not_found

        if final_address:

            # final_address, _ = Address.objects.get_or_create(
            #     user=user,
            #     **final_address
            # )
            # memo: 어떤 경우에든 같은 주소 정보가 중복이 되면 오류가 나는 것을 방지
            final_addresses = Address.objects.filter(user=user, **final_address)
            if final_addresses.exists():
                final_address = final_addresses.last()
            else:
                final_address = Address.objects.create(user=user, **final_address)
        else:
            validated_data.update({'mission_type_id': 2})
        obj = Mission.objects.create(user=user, final_address=final_address,
                                     **validated_data)

        if helper_obj:
            assigned = obj.bids.create(helper_id=helper_obj.id, is_assigned=True)
            # obj.request()
            obj.close()

        for stopover_data in stopovers:
            stopover_address = Address.objects.filter(user=user, **stopover_data).last()
            if not stopover_address:
                stopover_address = Address.objects.create(user=user, **stopover_data)
            obj.stopovers.add(stopover_address)

        for area_data in request_areas:
            obj.request_areas.add(area_data)
        return obj

    def save(self, **kwargs):
        banned = BannedWord.objects.check_words(self.validated_data['content'])
        if banned:
            raise Errors.invalid_content('"%s"는 미션내용에 사용할 수 없는 단어입니다.' % ', '.join(banned))
        else:
            return super(MissionSerializer, self).save(**kwargs)


class MissionReadOnlySerializer(MissionSerializer):
    stopovers = serializers.SerializerMethodField()
    final_address = AddressSerializer()
    can_create_review = serializers.SerializerMethodField(method_name='get_can_create_review')
    mobile_to_call = serializers.SerializerMethodField(method_name='get_mobile_to_call')

    def get_stopovers(self, instance):
        stopovers = instance.stopovers.all().order_by('missions_mission_stopovers.id')
        return AddressSerializer(stopovers, many=True).data

    def get_can_create_review(self, instance):
        active_bid = instance.active_bid
        if not active_bid:
            return False
        before_2_days = timezone.now() - timezone.timedelta(days=2)
        if not active_bid.done_datetime or active_bid.done_datetime < before_2_days:
            return False
        return not Review.objects.filter(created_user=self.context['request'].user, bid_id=active_bid.id).exists()

    def get_has_created_review(self, instance):
        return Review.objects.filter(
            created_user=self.context['request'].user,
            bid_id=instance.active_bid.id,
            is_active=True
        ).exists()

    def get_mobile_to_call(self, instance):
        bid = instance.active_bid
        if bid:
            user = self.context['request'].user
            if user.mobile != instance.user.mobile:
                return bid.customer_mobile
            if user.mobile != bid.helper.user.mobile:
                return bid.helper_mobile
        return ''

    class Meta:
        model = Mission
        fields = (
            'id', 'code', 'user', 'is_web', 'mission_type', 'content', 'due_datetime', 'is_due_date_modifiable',
            'is_due_time_modifiable', 'stopovers', 'final_address', 'request_areas', 'product', 'budget',
            'amount_high', 'amount_low', 'charge_rate', 'bid_limit_datetime', 'active_due', 'state', 'files',
            'assigned_helper', 'warnings', 'requested_datetime', 'assigned_bid_ids', 'bidded_count', 'bidded_lowest',
            'can_create_review', 'mobile_to_call', 'customer_coupon_used',
            'customer_paid', 'customer_point_used', 'bid_canceled_datetime', 'bid_done_datetime', 'push_result'
        )
        extra_kwargs = {
            'requested_datetime': {'read_only': True},
            'due_datetime': {'write_only': True},
            'bid_limit_datetime': {'read_only': True}
        }


class MissionAvailableSerializer(serializers.ModelSerializer):
    """
    실시간 미션 목록용 시리얼라이져
    """

    class Meta:
        model = Mission
        fields = (
            'id', 'code', 'mission_type_id', 'content', 'budget', 'final_address_area_id',
            'amount_high', 'amount_low', 'bid_limit_datetime', 'active_due', 'state', 'bidded_count'
        )


class BidSerializer(serializers.ModelSerializer):
    """
    미션 입찰 시리얼라이져
    """
    state = serializers.CharField(read_only=True)
    due_datetime = serializers.DateTimeField(write_only=True, required=False)
    active_due = serializers.CharField(read_only=True)
    helper = HelperReadOnlySerializer(read_only=True, required=False)
    location = serializers.SerializerMethodField('get_location', read_only=True, required=False)

    def get_location(self, instance):
        return instance.get_location_display()

    class Meta:
        model = Bid
        fields = ('id', 'amount', 'helper', 'applied_datetime', 'content', 'due_datetime', 'active_due',
                  'latitude', 'longitude', 'location', 'state')
        extra_kwargs = {
            'helper': {'read_only': True},
            'applied_datetime': {'read_only': True},
            'latitude': {'write_only': True},
            'longitude': {'write_only': True},
            'location': {'read_only': True},
            # 'is_assigned': {'read_only': True},
        }


class AnytalkBidSerializer(BidSerializer):
    """
    애니톡용 미션 입찰 시리얼라이져
    """
    mission = MissionReadOnlySerializer(read_only=True)
    area_mission = MultiAreaMissionSerializer(read_only=True)

    class Meta:
        model = Bid
        fields = ('id', 'mission', 'area_mission', 'amount', 'helper', 'applied_datetime',
                  'content', 'due_datetime', 'active_due', 'state')
        extra_kwargs = {
            'helper': {'read_only': True},
            'applied_datetime': {'read_only': True},
        }


class UserBidSerializer(BidSerializer):
    """
    사용자 미션 입찰 시리얼라이져
    """
    mission = MissionReadOnlySerializer(read_only=True)
    area_mission = MultiAreaMissionSerializer(read_only=True)
    canceled_datetime = serializers.DateTimeField(read_only=True, required=False)
    done_datetime = serializers.DateTimeField(read_only=True, required=False)
    can_create_review = serializers.SerializerMethodField(method_name='get_can_create_review')
    mobile_to_call = serializers.SerializerMethodField(method_name='get_mobile_to_call')

    class Meta:
        model = Bid
        fields = ('id', 'mission', 'area_mission', 'amount', 'is_assigned', 'applied_datetime', 'due_datetime',
                  'payment', 'state', 'canceled_datetime', 'done_datetime', 'can_create_review', 'mobile_to_call')
        extra_kwargs = {
            'helper': {'read_only': True},
            'applied_datetime': {'read_only': True},
            'is_assigned': {'read_only': True},
        }

    def get_can_create_review(self, instance):
        before_2_days = timezone.now() - timezone.timedelta(days=2)
        if not instance._done_datetime or instance._done_datetime < before_2_days:
            return False
        return not Review.objects.filter(created_user=self.context['request'].user, bid_id=instance.id).exists()

    def get_mobile_to_call(self, instance):
        user = self.context['request'].user
        if instance.mission:
            if user == instance.mission.user:
                return instance.helper_mobile
            if user == instance.helper.user:
                return instance.customer_mobile
        if instance.area_mission:
            if user == instance.area_mission.parent.user:
                return instance.helper.user.mobile
            if user == instance.helper.user:
                return instance.area_mission.parent.user.mobile
        return ''

class BidFileSerializer(serializers.ModelSerializer):
    """
    미션 수행중 애니톡 교환 파일 시리얼라이져
    """
    class Meta:
        model = BidFile
        fields = ('id', 'attach')


class InteractionSerializer(serializers.ModelSerializer):
    """
    미션 인터랙션 시리얼라이져
    """
    receiver = ProfileCodeSerializer(read_only=True, required=False)
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Interaction
        fields = ('id', 'interaction_type', 'detail', 'state', 'created_user', 'receiver')


class ReviewSerializer(serializers.ModelSerializer):
    """
    리뷰 시리얼라이져
    """
    bid = UserBidSerializer(read_only=True)
    created_user = ProfilePhotoSerializer(required=False, read_only=True)
    received_user = ProfilePhotoSerializer(required=False, read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'bid', 'stars', 'content', 'created_datetime', 'created_user', 'received_user')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
        }


class ReportSerializer(serializers.ModelSerializer):
    """
    신고 시리얼라이져
    """
    bid = UserBidSerializer(read_only=True)
    created_user = ProfileCodeSerializer(required=False, read_only=True)

    class Meta:
        model = Report
        fields = ('id', 'bid', 'content', 'created_datetime', 'created_user')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'created_user': {'read_only': True},
        }


class UserBlockSerializer(serializers.ModelSerializer):
    """
    사용자 차단 시리얼라이져
    """
    user = ProfileCodeSerializer(required=False, read_only=True)
    # created_user = ProfileCodeSerializer(required=False, read_only=True)

    class Meta:
        model = UserBlock
        fields = ('id', 'user', 'related_mission', 'created_datetime')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
        }


class FavoriteUserSerializer(serializers.ModelSerializer):
    """
    사용자 찜 시리얼라이져
    """
    user = ProfileCodeSerializer(required=False, read_only=True)
    helper = HelperReadOnlySerializer(read_only=True, required=False)

    class Meta:
        model = FavoriteUser
        fields = ('id', 'user', 'helper', 'created_datetime')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
        }


class ReportRequestBody(serializers.ModelSerializer):
    """
    신고 request body
    """
    class Meta:
        model = Report
        fields = ('content',)


class ReviewRequestBody(serializers.ModelSerializer):
    """
    리뷰 request body
    """
    class Meta:
        model = Review
        fields = ('stars', 'content',)


class UserBlockRequestBody(serializers.ModelSerializer):
    """
    사용자 차단 request body
    """
    code = serializers.CharField(label='회원코드')

    class Meta:
        model = UserBlock
        fields = ('code', 'related_mission',)


class FavoriteUserRequestBody(serializers.Serializer):
    """
    사용자 찜 request body
    """
    code = serializers.CharField(label='회원코드')


# class PenaltyPointSerializer(serializers.ModelSerializer):
#     """
#     벌점 시리얼라이져
#     """
#     mission = MissionSerializer(read_only=True)
#
#     class Meta:
#         model = PenaltyPoint
#         fields = ('id', 'reason', 'point', 'mission', 'detail', 'created_datetime')
#         extra_kwargs = {
#             'created_datetime': {'read_only': True},
#         }


class TemplateCategorySerializer(serializers.ModelSerializer):
    """
    템플릿 카테고리 시리얼라이져
    """
    class Meta:
        model = TemplateCategory
        fields = ('id', 'name', 'fullname')


class TemplateTagSerializer(serializers.ModelSerializer):
    """
    템플릿 태그 시리얼라이져
    """
    image = FullURLField(read_only=True)

    class Meta:
        model = TemplateTag
        fields = ('name', 'image')


class TemplateQuestionSerializer(serializers.ModelSerializer):
    """
    미션 템플릿 질문 시리얼라이져
    """
    class Meta:
        model = TemplateQuestion
        fields = ('id', 'question_type', 'name', 'title', 'description', 'select_options', 'has_etc_input', 'is_required')


class TemplateSerializer(serializers.ModelSerializer):
    """
    미션 템플릿 시리얼라이져
    """
    image = FullURLField(read_only=True)

    class Meta:
        model = MissionTemplate
        fields = ('id', 'name', 'image')


class TemplateWithTagsSerializer(serializers.ModelSerializer):
    """
    미션 템플릿 (카테고리 표시) 시리얼라이져
    """
    tags = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()  # todo: 카테고리 관련된 항목들은 추후 삭제할 것.

    class Meta:
        model = MissionTemplate
        fields = ('id', 'name', 'image', 'tags', 'category')

    def get_tags(self, obj):
        return obj.tag_list

    def get_category(self, obj):
        return {
            'id': obj.category_id,
            'fullname': str(obj.category)
        }


class TemplateMissionSerializer(serializers.Serializer):
    """
    템플릿 미션 생성용 시리얼라이져
    """
    data = serializers.ListField('템플릿 요청 데이터')



"""
홈 화면용 시리얼라이져 캐싱
"""


class CustomerHomeMissionSerializer(MissionReadOnlySerializer):
    """
    고객 홈 표시용 미션 시리얼라이져
    """
    active_bid_amount = serializers.IntegerField(read_only=True)
    final_address_area = serializers.CharField(source='final_address.area', read_only=True)
    # thumbnail = serializers.CharField(read_only=True)
    thumbnail = FullURLField(source='image_at_home', read_only=True)

    class Meta:
        model = Mission
        fields = ('id', 'code', 'final_address_area', 'content', 'bidded_count', 'active_bid_amount', 'thumbnail')

    @classmethod
    def cache(cls):
        anyman = CachedProperties()
        if type(anyman.customer_home) is not dict:
            anyman.customer_home = {}
        try:
            anyman.customer_home['missions'] = cls(Mission.objects.filter(is_at_home=True), many=True).data
        except:
            pass


class CustomerHomeTemplateSerializer(TemplateSerializer):
    """
    고객 홈 표시용 미션 템플릿 시리얼라이져
    """

    @classmethod
    def cache(cls):
        anyman = CachedProperties()
        if type(anyman.customer_home) is not dict:
            anyman.customer_home = {}
        try:
            anyman.customer_home['new_templates'] = cls(MissionTemplate.objects.get_recent(), many=True).data
        except:
            pass


class CustomerHomeReviewSerializer(serializers.ModelSerializer):
    """
    고객 홈 리뷰 시리얼라이져
    """
    template_name = serializers.SerializerMethodField(required=False, read_only=True)
    created_username = serializers.SerializerMethodField(required=False, read_only=True)

    class Meta:
        model = Review
        fields = ('template_name', 'stars', 'content', 'created_datetime', 'created_username')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
        }

    def get_template_name(self, instance):
        return instance.bid.mission.template.name

    def get_created_username(self, instance):
        return instance.created_user.username[:2] + '***'

    @classmethod
    def cache(cls):
        anyman = CachedProperties()
        if type(anyman.customer_home) is not dict:
            anyman.customer_home = {}
        reviews = Review.objects.get_template_reviews().get_helper_received().order_by('-created_datetime')[:20]
        try:
            anyman.customer_home['reviews'] = cls(reviews, many=True).data
        except:
            pass
        
class ReviewTemporarySerializer(serializers.ModelSerializer):
    created_user = ProfilePhotoSerializer(required=False, read_only=True)
    received_user = ProfilePhotoSerializer(required=False, read_only=True)
    class Meta:
        model = Review
        fields = ('id', 'stars', 'content', 'created_datetime', 'created_user', 'received_user')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
        }

class MissionReadOnlyTemporarySerializer(MissionReadOnlySerializer):
    class Meta(MissionReadOnlySerializer.Meta):
        fields =  MissionReadOnlySerializer.Meta.fields + ('template', 'template_data',)

class UserBidTemporarySerializer(UserBidSerializer):
    """
    사용자 미션 입찰 시리얼라이져
    """
    list_reviews = ReviewTemporarySerializer(many=True, read_only=True, source='reviews')
    mission = MissionReadOnlyTemporarySerializer(read_only=True)

    class Meta(UserBidSerializer.Meta):
        fields = UserBidSerializer.Meta.fields + ('list_reviews',)

