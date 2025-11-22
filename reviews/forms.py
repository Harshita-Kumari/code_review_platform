# reviews/forms.py
from django import forms

LANG_CHOICES = [
    ("python", "Python"),
    ("javascript", "JavaScript"),
    ("java", "Java"),
    ("c", "C"),
    ("cpp", "C++"),
]

class SubmissionForm(forms.Form):
    title = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Short title (optional)"}),
    )
    language = forms.ChoiceField(choices=LANG_CHOICES, initial="python")
    code = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 18, "placeholder": "Paste your code here..."}
        ),
        required=False,
    )
    upload = forms.FileField(required=False)

    # NEW: GitHub repo URL
    repo_url = forms.URLField(
        required=False,
        label="GitHub repository URL",
        widget=forms.URLInput(
            attrs={"placeholder": "https://github.com/username/repo or repo/tree/branch"}
        ),
    )
