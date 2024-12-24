from django import forms


class RequestBaseForm(forms.ModelForm):
    """
    리퀘스트 포함하는 폼
    """

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(RequestBaseForm, self).__init__(*args, **kwargs)
