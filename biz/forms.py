import datetime

from django import forms

from .models import Partnership, Campaign, LOCATIONS


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'tabIndex': '1', })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control form-control-lg', 'tabIndex': '2', })
    )


def min_length_3_validator(value):
    if len(value) < 3:
        raise forms.ValidationError('3글자 이상 입력해주세요')


class JoinForm(forms.ModelForm):
    sido = forms.CharField(widget=forms.TextInput(attrs={'type': 'hidden'}), required=False)
    sigungu = forms.CharField(widget=forms.TextInput(attrs={'type': 'hidden'}), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tel'].widget.attrs.update({'class': 'form-control'})
        self.fields['code'].widget.attrs.update({'class': 'form-control'})
        self.fields['name'].widget.attrs.update({'class': 'form-control'})
        self.fields['address_area'].widget.attrs.update({'class': 'form-control'})
        self.fields['address_detail'].widget.attrs.update({'class': 'form-control', 'required': 'required'})

    class Meta:
        model = Partnership
        fields = ['name', 'business_number', 'tel', 'address_detail', 'business_registration_photo',
                  'address_area', 'code', 'sido', 'sigungu']
        widgets = {
            'business_number': forms.NumberInput(attrs={'class': 'form-control', 'required': 'required'}),
            'business_registration_photo': forms.FileInput(attrs={'class': 'form-control'}),
        }
        error_messages = {
            'business_number': {
                'unique': '해당 사업자번호는 이미 존재합니다.',
            },
            'code': {
                'invalid': '영문, 숫자, "_", "-" 만 사용하실 수 있습니다.',
                'unique': '이미 존재하는 코드입니다. 다른 코드를 입력해주세요',
            },
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        black_list = ['admin']
        if code in black_list:
            raise forms.ValidationError(f'{code} 코드는 사용하실 수 없습니다.')
        return code


class CampaignBannerForm(forms.Form):
    image = forms.ImageField(
        widget=forms.FileInput(attrs={'multiple': True, 'class': 'form-control', 'style': 'display:none'}),
        required=False)
    location = forms.CharField(widget=forms.TextInput(attrs={'type': 'hidden'}), required=False)


class CampaignQuestionForm(forms.ModelForm):
    campaign_questions = forms.CharField(widget=forms.Textarea(attrs={'style': 'display: none;'}), required=False)


class CampaignForm(CampaignBannerForm, CampaignQuestionForm, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            del self.fields['campaign_type']
        else:
            self.fields['campaign_type'].widget.attrs.update({'class': 'form-control'})
        self.fields['title'].widget.attrs.update({'class': 'form-control'})
        self.fields['end_datetime'].widget.attrs.update({'min': datetime.datetime.today().strftime("%Y-%m-%d")})
        self.fields['start_datetime'].widget.attrs.update({'placeholder': '시작일을 선택해주세요'})

    class Meta:
        model = Campaign
        fields = ['campaign_type', 'title', 'start_datetime', 'end_datetime']
        widgets = {
            'campaign_type': forms.Select(attrs={'required': False}),
            'start_datetime': forms.DateInput(attrs={'class': 'form-control', 'type': 'date',
                                                     'placeholder': '시작일을 선택해주세요', 'required': 'required'}),
            'end_datetime': forms.DateInput(attrs={'class': 'form-control',
                                                   'placeholder': '종료일을 선택해주세요', 'type': 'date'}),
        }

    def clean_end_datetime(self):
        start_datetime = self.cleaned_data.get('start_datetime')
        end_datetime = self.cleaned_data['end_datetime']
        if start_datetime and end_datetime and end_datetime < start_datetime:
            raise forms.ValidationError(f'시작일인 {start_datetime.strftime("%Y-%m-%d")} 이전 날짜는 선택하실 수 없습니다.')
        return end_datetime


class CampaignCreateForm(CampaignForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['start_datetime'].widget.attrs.update({'min': datetime.datetime.today().strftime("%Y-%m-%d")})

    def clean_start_datetime(self):
        start_datetime = self.cleaned_data['start_datetime']
        today = datetime.datetime.today()
        if today > (start_datetime + datetime.timedelta(days=1)):
            raise forms.ValidationError(f'{today.strftime("%Y-%m-%d")} 이전 날짜는 선택하실 수 없습니다.')
        return start_datetime
