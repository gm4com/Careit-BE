from django.conf import settings
from django.utils import timezone

from rest_framework import mixins, response, parsers
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from common.utils import CachedProperties
from common.admin import log_with_reason
from common.views import swagger_auto_boolean_schema
from common.exceptions import Errors
from accounts import permissions
from base.views import BaseModelViewSet
from .models import BOARD_IDS, BOARD_FUNCTIONS, Writing, Comment, AttachFile
from .serializers import (
    AttachFileSerializer, CommentSerializer, WritingRequestBody,
    ContactWritingSerializer, PartnershipWritingSerializer, NoticeWritingSerializer,
    EventWritingSerializer, MagazineWritingSerializer, WebtoonWritingSerializer, FAQWritingSerializer,
    ArticleWritingSerializer
)


anyman = CachedProperties()


class BoardPagination(LimitOffsetPagination):
    default_limit = 3


class BoardViewSet(mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.CreateModelMixin,
                   mixins.UpdateModelMixin,
                   BaseModelViewSet):
    """
    게시판 글 API endpoint
    """
    model = Writing
    serializer_classes = {
        'contact': ContactWritingSerializer,
        'partnership': PartnershipWritingSerializer,
        'customer_notice': NoticeWritingSerializer,
        'helper_notice': NoticeWritingSerializer,
        'customer_event': EventWritingSerializer,
        'helper_event': EventWritingSerializer,
        'magazine': MagazineWritingSerializer,
        'webtoon': WebtoonWritingSerializer,
        'faq': FAQWritingSerializer,
        'article': ArticleWritingSerializer,
    }
    http_method_names = ['get', 'post', 'patch']
    permission_classes = (permissions.IsValidUser,)
    lookup_url_kwarg = 'post_id'
    lookup_field = 'id'

    def dispatch(self, request, *args, **kwargs):
        self.board = self.kwargs.get('board')
        if self.board == 'faq':
            self.pagination_class = None
        if self.board == 'article':
            self.pagination_class = BoardPagination
        return super(BoardViewSet, self).dispatch(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            self.permission_classes = (permissions.AllowAny,)
        return super(BoardViewSet, self).get_permissions()

    def get_serializer_class(self):
        return self.serializer_classes[self.board]

    def check(self):
        if not self.board or self.board not in BOARD_IDS:
            raise Errors.not_found

    def check_write_perm(self):
        self.check()
        if 'user_create' not in BOARD_FUNCTIONS[BOARD_IDS[self.board]]:
            raise Errors.permission_denied

    def get_queryset(self):
        self.check()
        qs = super(BoardViewSet, self).get_queryset().filter(board=BOARD_IDS[self.board])
        if self.board in ('contact', 'partnership'):
            qs = qs.filter(created_user_id=self.request.user.id)
        if self.board.startswith('customer_'):
            qs = qs.filter(location__location='customer')
        if self.board.startswith('helper_'):
            qs = qs.filter(location__location='helper')
        return qs.order_by('-id')

    def retrieve(self, request, *args, **kwargs):
        if self.board in ('contact', 'partnership', 'faq'):
            return super(BoardViewSet, self).retrieve(request, *args, **kwargs)
        obj = self.get_object()
        return response.Response(data=self.get_serializer_class()(instance=obj.read()).data)

    @swagger_auto_schema(request_body=WritingRequestBody)
    def create(self, request, *args, **kwargs):
        self.check_write_perm()
        request.data.update({
            'board': BOARD_IDS[self.board],
            'created_user': request.user,
        })
        serializer_class = self.get_serializer_class()
        obj = serializer_class().create(request.data)
        log_with_reason(request.user, obj, 'added')
        if serializer_class == PartnershipWritingSerializer:
            url = 'https://%s/admin/board/partnershipwriting/%s/change' % (settings.MAIN_HOST, obj.id)
            anyman.slack.channel('anyman__17-1').script_msg(
                '%s' % obj.title,
                '%s\n%s' % (url, obj.content)
            )
        return response.Response(data=serializer_class(instance=obj).data)

    @swagger_auto_schema(request_body=WritingRequestBody)
    def partial_update(self, request, *args, **kwargs):
        self.check_write_perm()
        obj = self.get_object()
        if obj.created_user_id == request.user.id:
            obj.updated_datetime = timezone.now()
            obj.save()
        log_with_reason(request.user, obj, 'changed')
        return super(BoardViewSet, self).partial_update(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        res = super(BoardViewSet, self).finalize_response(request, response, *args, **kwargs)
        if res.status_code < 300 and res.data is not None and self.board == 'article' and 'post_id' not in kwargs:
            res.data = res.data['data']
            res.data['data'] = res.data.pop('results')
        # if request.user.is_authenticated:
        #     res.data['is_blocked'] = request.user.is_blocked
        # todo: 현재 토큰의 유효성 검사 추가
        return res



class AttachFileViewSet(mixins.CreateModelMixin,
                        mixins.DestroyModelMixin,
                        BaseModelViewSet):
    """
    첨부파일 API endpoint
    """
    model = AttachFile
    serializer_class = AttachFileSerializer
    parser_classes = (parsers.MultiPartParser,)

    def dispatch(self, request, *args, **kwargs):
        self.board = self.kwargs.get('board')
        self.writing_id = self.kwargs.get('post_id')
        return super(AttachFileViewSet, self).dispatch(request, *args, **kwargs)

    def check(self):
        if self.board not in BOARD_IDS:
            raise Errors.not_found

    def check_write_perm(self):
        self.check()
        if not {'user_create', 'attach'}.issubset(BOARD_FUNCTIONS[BOARD_IDS[self.board]]):
            raise Errors.permission_denied

    def get_queryset(self):
        self.check()
        qs = super(AttachFileViewSet, self).get_queryset().filter(
            writing__board=BOARD_IDS[self.board],
            writing_id=self.writing_id
        )
        if self.action == 'destroy':
            qs = qs.filter(writing__user=self.request.user)
        return qs

    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def create(self, request, *args, **kwargs):
        self.check_write_perm()
        file_obj = request.data['attach']
        obj = self.model.objects.create(writing_id=self.writing_id)
        filename = obj.handle_attach(file_obj)
        url = request.build_absolute_uri(settings.MEDIA_URL + filename)
        return response.Response({'attach': url})


class CommentViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin,
                     BaseModelViewSet):
    """
    코멘트 API endpoint
    """
    model = Comment
    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'patch', 'delete']

    def dispatch(self, request, *args, **kwargs):
        self.board = self.kwargs.get('board')
        self.writing_id = self.kwargs.get('post_id')
        return super(CommentViewSet, self).dispatch(request, *args, **kwargs)

    def check(self):
        if self.board not in BOARD_IDS:
            raise Errors.not_found
        try:
            self.writing = Writing.objects.get(board=BOARD_IDS[self.board], id=self.writing_id)
        except:
            raise Errors.not_found
        if 'comment' not in BOARD_FUNCTIONS[BOARD_IDS[self.board]]:
            raise Errors.permission_denied

    def get_queryset(self):
        self.check()
        qs = super(CommentViewSet, self).get_queryset().filter(
            writing__board=BOARD_IDS[self.board],
            writing_id=self.writing_id
        )
        if self.action == 'destroy':
            qs = qs.filter(created_user=self.request.user)
        return qs

    @swagger_auto_schema(responses={400: Errors.fields_invalid.as_p()})
    def create(self, request, *args, **kwargs):
        self.check()
        request.data.update({
            'writing': self.writing,
            'created_user': request.user,
        })
        obj = self.serializer_class().create(request.data)
        log_with_reason(request.user, obj, 'added')
        return response.Response(data=self.serializer_class(instance=obj).data)

    @swagger_auto_schema(request_body=WritingRequestBody)
    def partial_update(self, request, *args, **kwargs):
        self.check()
        obj = self.get_object()
        if obj.created_user_id == request.user.id:
            obj.updated_datetime = timezone.now()
            obj.save()
        log_with_reason(request.user, obj, 'changed')
        return super(CommentViewSet, self).partial_update(request, *args, **kwargs)

