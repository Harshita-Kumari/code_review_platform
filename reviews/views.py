from django.shortcuts import render, redirect
from django.urls import reverse
from .forms import SubmissionForm
from .models import Submission, Review
from .prompts import build_review_prompt
from .llm_client import call_llm
import json, re

def index(request):
    form = SubmissionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"]
        language = form.cleaned_data["language"]
        code = form.cleaned_data["code"] or ""
        upload = request.FILES.get("upload")
        if upload:
            file_content = upload.read().decode("utf-8", errors="ignore")
            code = code + "\n\n" + file_content

        sub = Submission.objects.create(title=title, language=language, code=code, user=request.user if request.user.is_authenticated else None)

        prompt = build_review_prompt(code, language)
        try:
            raw = call_llm(prompt)
        except Exception as e:
            form.add_error(None, f"LLM request failed: {e}")
            return render(request, "reviews/index.html", {"form": form})

        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = {"raw": raw}
            else:
                parsed = {"raw": raw}

        review = Review.objects.create(
            submission=sub,
            summary=parsed.get("summary", "") if isinstance(parsed, dict) else "",
            issues=parsed.get("issues", []) if isinstance(parsed, dict) else [],
            suggestions=parsed.get("suggestions", []) if isinstance(parsed, dict) else [],
            tests_suggestions=parsed.get("tests_suggestions", "") if isinstance(parsed, dict) else "",
            quality_score=parsed.get("quality_score", None) if isinstance(parsed, dict) else None,
            raw_response={"raw": raw},
            processed=True,
        )

        return redirect(reverse("reviews:detail", kwargs={"pk": review.id}))

    return render(request, "reviews/index.html", {"form": form})

def detail(request, pk):
    review = Review.objects.get(id=pk)
    return render(request, "reviews/result.html", {"review": review})

def history(request):
    subs = Submission.objects.order_by("-created_at")[:50]
    return render(request, "reviews/history.html", {"subs": subs})

