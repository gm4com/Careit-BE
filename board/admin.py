from django.contrib import admin, messages
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.shortcuts import redirect, reverse
from django.db.models import Count

from django_summernote.admin import SummernoteModelAdminMixin

from common.admin import AdminFilter, ChangeFormSplitMixin, AdditionalAdminUrlsMixin
from base.admin import BaseAdmin
from missions.models import Mission, MultiMission
from .models import (
    BOARD_IDS, Comment, Answer, AttachFile, TitleImage, ViewLocation, ViewTerm,
    ContactWriting, PartnershipWriting, NoticeWriting, EventWriting, MagazineWriting, WebtoonWriting, FAQWriting,
    ArticleWriting
)
from notification.models import Notification, ReceiverGroup


"""
filters
"""


class CreatedAdminUserFilter(AdminFilter):
    """
    작성 관리자 필터
    """
    title = '작성 직원'
    parameter_name = 'created_user'


"""
inlines
"""


class AnswerInline(admin.TabularInline):
    model = Answer
    fields = ('content',)
    extra = 0
    min_num = 1


class CommentReadOnlyInline(admin.TabularInline):
    model = Comment
    fields = ('content', 'created_user', 'created_datetime')
    readonly_fields = ('content', 'created_user', 'created_datetime')
    extra = 0
    min_num = 1

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class AttachFileReadOnlyInline(admin.TabularInline):
    model = AttachFile
    extra = 0
    fields = ('attach',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super(AttachFileReadOnlyInline, self).get_queryset(request).filter(is_active=True)


class TitleImageInline(admin.TabularInline):
    model = TitleImage
    extra = 1
    max_num = 1
    fields = ('attach',)

    def get_queryset(self, request):
        return super(TitleImageInline, self).get_queryset(request).filter(is_active=True)


class ViewLocationInline(admin.TabularInline):
    model = ViewLocation
    extra = 1
    max_num = 1


class ViewTermInline(admin.StackedInline):
    model = ViewTerm
    extra = 1
    max_num = 1


"""
admins
"""


class WritingAdmin(ChangeFormSplitMixin, BaseAdmin):
    """
    게시판 글 어드민
    """
    board = None
    # summernote_fields = ('content',)

    def save_form(self, request, form, change):
        obj = super(WritingAdmin, self).save_form(request, form, change)
        if not obj.board:
            obj.board = BOARD_IDS[self.board]
        if change and obj.created_user_id == request.user.id:
            obj.updated_datetime = timezone.now()
        if not change and not obj.created_user:
            obj.created_user = request.user
        return obj

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        if obj:
            obj.content = mark_safe(obj.content)
        return super(WritingAdmin, self).render_change_form(request, context, add, change, form_url, obj)

    def save_formset(self, request, form, formset, change):
        obj = form.save()
        if formset.model is TitleImage:
            for f in formset.forms:
                if 'attach' in f.changed_data:
                    attach_obj = f.save(commit=False)
                    attach_obj.writing_id = obj.id
                    attach_obj.save()
                    attach_obj.handle_attach(f.cleaned_data['attach'])
        return super(WritingAdmin, self).save_formset(request, form, formset, change)


class ContactAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    1:1 문의 추가 어드민
    """

    def get_additional_urls(self):
        return {
            'redirect_mission': 'redirect/<mission_code>',
        }

    def view_redirect_mission(self, request, *args, **kwargs):
        mission_code = kwargs.get('mission_code')
        mission = Mission.objects.filter(code=mission_code).last() or \
                  MultiMission.objects.filter(code=mission_code).last()
        if not mission:
            messages.error(request, '코드에 해당하는 미션을 찾을 수 없습니다.')
            return self.redirect_referer(request)
        return redirect('admin:missions_%s_change' % mission._meta.model_name, object_id=mission.id)


@admin.register(ContactWriting)
class ContactAdmin(ContactAdditionalAdmin, WritingAdmin):
    """
    1:1 문의 어드민
    """
    board = 'contact'
    list_display = ('title', 'get_related_mission_display', 'created_user', 'created_datetime', 'get_comments_count')
    inlines = (AnswerInline,)

    def get_queryset(self, request):
        qs = super(ContactAdmin, self).get_queryset(request)
        return qs.annotate(comment_count=Count('comments'))

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')

    def get_related_mission_display(self, obj):
        return mark_safe('<a href="%s" class="btn btn-sm btn-info">%s</a>' % (
            reverse('admin:board_contactwriting_redirect_mission', kwargs={'mission_code': obj.subtitle}),
            obj.subtitle
        )) if obj.subtitle else ''
    get_related_mission_display.short_description = '관련 미션'
    get_related_mission_display.admin_order_field = 'subtitle'

    def get_comments_count(self, obj):
        return obj.comment_count
    get_comments_count.short_description = '답변개수'
    get_comments_count.admin_order_field = 'comment_count'


@admin.register(PartnershipWriting)
class PartnershipAdmin(WritingAdmin):
    """
    제휴/제안 어드민
    """
    board = 'partnership'
    list_display = ('title', 'created_user', 'created_datetime')
    inlines = (AttachFileReadOnlyInline, AnswerInline)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')


class NoticeAdditionalAdmin(AdditionalAdminUrlsMixin):
    """
    공지 추가 어드민
    """
    def get_additional_urls(self):
        return {
            'add_notification': '<id>/add_notification/',
        }

    def view_add_notification(self, request, *args, **kwargs):
        obj = self._get_object_or_fail(kwargs)
        groups_by_location = {
            'customer': ['not_helper'],
            'helper': ['helperonly'],
            '': ['alluser']
        }
        location = obj.location.location if hasattr(obj, 'location') else ''
        group_receivers = ReceiverGroup.objects.filter(code__in=groups_by_location[location])
        Notification.objects.no_send_push(group_receivers, '공지사항', obj.title, data={
            'page': 'NOTICE_DETAIL',
            'obj_id': obj.id
        }, request=request)
        return self.redirect_referer(request)


@admin.register(NoticeWriting)
class NoticeAdmin(NoticeAdditionalAdmin, WritingAdmin):
    """
    공지 어드민
    """
    board = 'notice'
    list_display = ('title', 'get_location_display', 'created_user', 'created_datetime')
    list_filter = (CreatedAdminUserFilter,)
    inlines = (TitleImageInline, ViewLocationInline,)
    change_form_template = 'admin/board/noticewriting/change_form.html'

    def get_fields(self, request, obj=None):
        if obj:
            return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')
        else:
            return ('title', 'content')

    def get_readonly_fields(self, request, obj=None):
        return ('created_user', 'created_datetime', 'updated_datetime')

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        is_sent = Notification.objects.filter(send_method='push', data_page='NOTICE_DETAIL', data_obj_id=object_id).exists()
        extra_context.update({'view_notification_button': not is_sent})
        return super(NoticeAdmin, self).changeform_view(request, object_id=object_id, form_url=form_url, extra_context=extra_context)

    def get_location_display(self, obj):
        return str(obj.location) if hasattr(obj, 'location') else ''
    get_location_display.short_description = '노출 위치'
    get_location_display.admin_order_field = 'location__location'


@admin.register(EventWriting)
class EventAdmin(NoticeAdmin):
    """
    이벤트 어드민
    """
    board = 'event'
    inlines = (TitleImageInline, ViewLocationInline, ViewTermInline)


@admin.register(MagazineWriting)
class MagazineAdmin(WritingAdmin):
    """
    매거진 어드민
    """
    board = 'magazine'
    list_display = ('title', 'created_user', 'created_datetime')
    inlines = (TitleImageInline, CommentReadOnlyInline,)

    def get_fields(self, request, obj=None):
        if obj:
            return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')
        else:
            return ('title', 'content')

    def get_readonly_fields(self, request, obj=None):
        return ('created_user', 'created_datetime', 'updated_datetime')


@admin.register(WebtoonWriting)
class WebtoonAdmin(MagazineAdmin):
    """
    웹툰 어드민
    """
    board = 'webtoon'


@admin.register(FAQWriting)
class FAQAdmin(WritingAdmin):
    """
    FAQ 어드민
    """
    board = 'faq'
    list_display = ('title', 'created_user', 'created_datetime')
    inlines = (AnswerInline,)

    def get_fields(self, request, obj=None):
        if obj:
            return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')
        else:
            return ('title', 'content')

    def get_readonly_fields(self, request, obj=None):
        return ('created_user', 'created_datetime', 'updated_datetime')


@admin.register(ArticleWriting)
class ArticleAdmin(WritingAdmin):
    """
    보도자료 어드민
    """
    board = 'article'
    list_display = ('title', 'created_user', 'created_datetime')
    inlines = (TitleImageInline,)

    def get_fields(self, request, obj=None):
        if obj:
            return ('title', 'content', 'created_user', 'created_datetime', 'updated_datetime')
        else:
            return ('title', 'content')

    def get_readonly_fields(self, request, obj=None):
        return ('created_user', 'created_datetime', 'updated_datetime')

