from django.contrib.auth.mixins import AccessMixin
from django.shortcuts import redirect
from django.http.response import Http404
from biz.models import Partnership


class PartnershipMixin(AccessMixin):
    """
    파트너쉽 뷰 믹스인
    """
    login_url = 'biz:login'
    partnership = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_staff:
            self.partnerships = Partnership.objects.all()
        else:
            self.partnerships = Partnership.objects.get_by_user(request.user)

        code = kwargs.get('code')
        try:
            self.partnership = self.partnerships.get(code=code)
        except:
            raise Http404

        return super(PartnershipMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(PartnershipMixin, self).get_context_data(**kwargs)
        context['partnerships'] = self.partnerships
        context['partnership'] = self.partnership
        return context


class AcceptedPartnershipMixin(PartnershipMixin):
    """
    승인된 파트너쉽 뷰 믹스인
    """
    def dispatch(self, request, *args, **kwargs):
        rtn = super(AcceptedPartnershipMixin, self).dispatch(request, *args, **kwargs)
        if self.partnership and self.partnership.state != 'activated':
            return redirect('biz:profile', self.partnership.code)
        return rtn
