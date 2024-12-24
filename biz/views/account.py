import operator
from functools import reduce

from django.contrib import messages
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect
from django.views import View
from django.views.generic import FormView
from base.models import Area

from biz.forms import JoinForm, LoginForm
from biz.models import Partnership, PartnershipUserRelation


class Login(FormView):
    """
    애니비즈 로그인 뷰
    """
    template_name = 'biz/login.html'
    form_class = LoginForm

    def get(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            return redirect('biz:joined')
        return super().get(*args, **kwargs)

    def form_valid(self, form):
        email, password = form.cleaned_data['email'], form.cleaned_data['password']
        user = authenticate(email=email, password=password)
        if user:
            django_login(self.request, user)
            partnership_user_model = PartnershipUserRelation.objects.select_related('partnership', 'user'
                                                                                    ).filter(user=self.request.user)
            if len(partnership_user_model):
                return redirect('biz:joined')
            return redirect('biz:join')
        messages.error(self.request, 'ID 또는 암호를 다시 확인해주세요')
        return super(Login, self).form_invalid(form)


class LogoutView(View):

    def dispatch(self, request, *args, **kwargs):
        django_logout(request)
        return redirect('biz:login')


class JoinView(LoginRequiredMixin, FormView):
    """
    파트너쉽에 가입 신청 뷰
    """
    template_name = 'biz/join.html'
    form_class = JoinForm
    success_url = '/biz/'
    login_url = 'biz:login'

    @transaction.atomic
    def form_valid(self, form):
        area = None
        cleaned_data = form.cleaned_data
        area_list = [cleaned_data.pop('sigungu'), cleaned_data.pop('sido')]
        query_keyword = reduce(operator.and_, (Q(name__icontains=area)
                                               | Q(parent__name__icontains=area) for area in area_list))
        if area_list[0]:
            area = Area.objects.select_related('parent').filter(query_keyword)
            if not area:  # 주소 시,도 , 군, 구가 사라진 경우
                messages.error(self.request, '주소를 다시 선택해주시기 바랍니다.')
                return super().form_invalid(form)
        cleaned_data['address_area_id'] = area[0].id
        partnership, partnership_created = Partnership.objects.get_or_create(**cleaned_data)
        PartnershipUserRelation.objects.get_or_create(partnership=partnership, user=self.request.user)
        return redirect('biz:campaign-list', cleaned_data['code'])

    def form_invalid(self, form):
        for field in form.errors:
            form[field].field.widget.attrs['class'] += ' is-invalid'
        return super().form_invalid(form)
