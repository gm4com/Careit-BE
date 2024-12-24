from rest_framework import serializers

from common.exceptions import Errors
from accounts.serializers import ProfileCodeSerializer
from .models import (
    Writing, Comment, AttachFile, ViewTerm,
    ContactWriting, PartnershipWriting, NoticeWriting, EventWriting, MagazineWriting, WebtoonWriting, FAQWriting,
    ArticleWriting
)


class CommentSerializer(serializers.ModelSerializer):
    """
    코멘트 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)

    class Meta:
        model = Comment
        fields = ('id', 'content', 'created_user', 'created_datetime', 'updated_datetime')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class AttachFileSerializer(serializers.ModelSerializer):
    """
    첨부파일 시리얼라이져
    """
    class Meta:
        model = AttachFile
        fields = ('id', 'attach')


class ViewTermSerializer(serializers.ModelSerializer):
    """
    노출기간 시리얼라이져
    """
    class Meta:
        model = ViewTerm
        fields = ('start_date', 'end_date')


class WritingRequestBody(serializers.ModelSerializer):
    """
    게시글 request body
    """
    class Meta:
        model = Writing
        fields = ('title', 'subtitle', 'content')


class ContactWritingSerializer(serializers.ModelSerializer):
    """
    1:1 문의 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    comments = CommentSerializer(many=True, read_only=True, required=False)

    class Meta:
        model = ContactWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'created_datetime', 'updated_datetime', 'comments')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class PartnershipWritingSerializer(serializers.ModelSerializer):
    """
    제휴/제안 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    comments = CommentSerializer(many=True, read_only=True, required=False)
    files = AttachFileSerializer(many=True, read_only=True, required=False)

    class Meta:
        model = PartnershipWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'created_datetime', 'updated_datetime',
                  'comments', 'files')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class NoticeWritingSerializer(serializers.ModelSerializer):
    """
    공지 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    location = serializers.CharField(source='location.location')
    files = AttachFileSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = NoticeWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'files', 'created_datetime', 'updated_datetime',
                  'viewed_count', 'location')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class EventWritingSerializer(serializers.ModelSerializer):
    """
    이벤트 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    location = serializers.CharField(source='location.location')
    term = ViewTermSerializer(read_only=True, required=False)
    files = AttachFileSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = EventWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'files', 'created_datetime', 'updated_datetime',
                  'viewed_count', 'location', 'term')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class MagazineWritingSerializer(serializers.ModelSerializer):
    """
    매거진 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    files = AttachFileSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = MagazineWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'files', 'created_datetime',
                  'updated_datetime', 'viewed_count')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class WebtoonWritingSerializer(serializers.ModelSerializer):
    """
    웹툰 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    files = AttachFileSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = WebtoonWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'files', 'created_datetime',
                  'updated_datetime', 'viewed_count')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class FAQWritingSerializer(serializers.ModelSerializer):
    """
    FAQ 시리얼라이져
    """
    created_user = ProfileCodeSerializer(read_only=True, required=False)
    comments = CommentSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = FAQWriting
        fields = ('id', 'title', 'subtitle', 'content', 'created_user', 'created_datetime',
                  'updated_datetime', 'comments')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }


class ArticleWritingSerializer(serializers.ModelSerializer):
    """
    보도자료 시리얼라이져
    """
    files = AttachFileSerializer(many=True, read_only=True, required=False)
    content = serializers.CharField(read_only=True, source='parsed_content')

    class Meta:
        model = ArticleWriting
        fields = ('id', 'title', 'subtitle', 'content', 'files', 'created_datetime',
                  'updated_datetime', 'viewed_count')
        extra_kwargs = {
            'created_datetime': {'read_only': True},
            'updated_datetime': {'read_only': True},
        }
