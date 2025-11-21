# reviews/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from .forms import SubmissionForm
from .models import Submission, Review
from .prompts import build_review_prompt
from .llm_client import call_llm
import json, re, imghdr

def index(request):
    form = SubmissionForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"]
        language = form.cleaned_data["language"]
        code = form.cleaned_data["code"] or ""
        upload = request.FILES.get("upload")

        # Upload validation
        if upload:
            # size check
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                messages.error(request, f"Uploaded file is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).")
                return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

            # detect images by header bytes
            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                messages.error(request, "Detected an image file. Please upload a text code file (.py, .js, .java, .txt).")
                return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

            # simple extension guidance
            allowed_ext = (".py", ".js", ".java", ".txt", ".md")
            if not any(upload.name.lower().endswith(ext) for ext in allowed_ext):
                messages.warning(request, "Uploaded file extension is unusual for code. We'll try to read it but prefer .py/.js/.java/.txt.")

            try:
                file_content = upload.read().decode("utf-8", errors="ignore")
            except Exception:
                messages.error(request, "Unable to read uploaded file as text.")
                return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

            if len(code) + len(file_content) > settings.MAX_CODE_CHARS:
                messages.error(request, "Combined code too long. Please shorten the input.")
                return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

            code = code + "\n\n" + file_content

        if not code.strip():
            messages.error(request, "Please paste code or upload a small code file.")
            return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

        submission = Submission.objects.create(
            title=title,
            language=language,
            code=code,
            user=request.user if request.user.is_authenticated else None
        )

        # Build prompt and call LLM
        prompt = build_review_prompt(code, language)
        try:
            raw = call_llm(prompt)
        except Exception as e:
            messages.error(request, f"LLM request failed: {e}")
            return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})

        # Parse JSON from response with fallback
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
            submission=submission,
            summary=parsed.get("summary", "") if isinstance(parsed, dict) else "",
            issues=parsed.get("issues", []) if isinstance(parsed, dict) else [],
            suggestions=parsed.get("suggestions", []) if isinstance(parsed, dict) else [],
            tests_suggestions=parsed.get("tests_suggestions", "") if isinstance(parsed, dict) else "",
            quality_score=parsed.get("quality_score", None) if isinstance(parsed, dict) else None,
            raw_response={"raw": raw},
            processed=True
        )

        return redirect(reverse("reviews:detail", kwargs={"pk": review.id}))

    return render(request, "reviews/index.html", {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB})


def detail(request, pk):
    review = get_object_or_404(Review, id=pk)
    raw_text = ""
    if review.raw_response:
        raw_text = review.raw_response.get("raw", "")
    pretty_raw = raw_text
    try:
        parsed = json.loads(raw_text) if isinstance(raw_text, str) else None
        if parsed:
            pretty_raw = json.dumps(parsed, indent=2)
    except Exception:
        pass
    return render(request, "reviews/result.html", {"review": review, "pretty_raw": pretty_raw})


def history(request):
    subs = Submission.objects.order_by("-created_at")[:50]
    return render(request, "reviews/history.html", {"subs": subs})
