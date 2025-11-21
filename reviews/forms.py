from django import forms

LANG_CHOICES = [
    ("python", "Python"),
    ("javascript", "JavaScript"),
    ("java", "Java"),
]

class SubmissionForm(forms.Form):
    title = forms.CharField(max_length=255)
    language = forms.ChoiceField(choices=LANG_CHOICES)
    code = forms.CharField(widget=forms.Textarea(attrs={"rows":20}), required=False)
    upload = forms.FileField(required=False)
