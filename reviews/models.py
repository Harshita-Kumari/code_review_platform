from django.db import models
from django.contrib.auth import get_user_model

class Submission(models.Model):
    title = models.CharField(max_length=255)
    language = models.CharField(max_length=50, default="python")
    code = models.TextField()
    uploaded_file = models.FileField(upload_to="uploads/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(get_user_model(), null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.title} [{self.language}]"

class Review(models.Model):
    submission = models.ForeignKey(Submission, related_name="reviews", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    llm_model = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    issues = models.JSONField(null=True, blank=True)
    suggestions = models.JSONField(null=True, blank=True)
    tests_suggestions = models.TextField(blank=True)
    quality_score = models.FloatField(null=True, blank=True)
    raw_response = models.JSONField(null=True, blank=True)
    processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)

    def __str__(self):
        return f"Review {self.id} for {self.submission.title}"

