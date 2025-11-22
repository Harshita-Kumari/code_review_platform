# reviews/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages

from .forms import SubmissionForm
from .models import Submission, Review
from .prompts import build_review_prompt
from .llm_client import call_llm

import json
import re
import imghdr
import zipfile
import io

# allowed code extensions for both single files & zip contents
ALLOWED_CODE_EXT = (".py", ".js", ".java", ".txt", ".md")


def _iter_zip_code_files(upload_file, per_file_limit):
    """
    Yield (file_path, code_text) for each code file inside a ZIP.
    Only returns files with extension in ALLOWED_CODE_EXT.
    Truncates each file to per_file_limit characters.
    """
    data = upload_file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("Uploaded ZIP file is invalid or corrupted.")

    for info in zf.infolist():
        if info.is_dir():
            continue

        name = info.filename
        if not any(name.lower().endswith(ext) for ext in ALLOWED_CODE_EXT):
            # skip non-code files
            continue

        try:
            file_bytes = zf.read(info)
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            # skip unreadable files
            continue

        text = text.strip()
        if not text:
            continue

        if len(text) > per_file_limit:
            text = text[:per_file_limit]

        yield name, text


def index(request):
    form = SubmissionForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"] or "Untitled review"
        language = form.cleaned_data["language"]
        base_code = form.cleaned_data["code"] or ""
        upload = request.FILES.get("upload")

        # no upload: behave like before, review base_code only
        if not upload and not base_code.strip():
            messages.error(
                request, "Please paste code or upload a code file / ZIP project."
            )
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        # create submission early (represents whole review request / project)
        submission = Submission.objects.create(
            title=title,
            language=language,
            code=base_code or "",
            user=request.user if request.user.is_authenticated else None,
        )

        # ---------- CASE 1: ZIP PROJECT (per-file reviews) ----------
        if upload and upload.name.lower().endswith(".zip"):
            # file size limit
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                messages.error(
                    request,
                    f"Uploaded ZIP is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            # detect images (if somebody renamed image to .zip)
            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                messages.error(
                    request,
                    "Detected an image file. Please upload a real ZIP project or code file.",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            try:
                files = list(
                    _iter_zip_code_files(upload, per_file_limit=settings.MAX_CODE_CHARS)
                )
            except ValueError as e:
                messages.error(request, str(e))
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            if not files:
                messages.error(
                    request,
                    "No readable .py/.js/.java/.txt/.md files found inside ZIP.",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            created_reviews = []
            for file_path, file_code in files:
                # combine optional base_code (global context) + file code
                combined_code = base_code.strip()
                if combined_code:
                    combined_code += "\n\n"
                combined_code += f"# FILE: {file_path}\n{file_code}"

                if len(combined_code) > settings.MAX_CODE_CHARS:
                    combined_code = combined_code[: settings.MAX_CODE_CHARS]

                prompt = build_review_prompt(combined_code, language)
                try:
                    raw = call_llm(prompt)
                except Exception as e:
                    # record error but continue with other files
                    Review.objects.create(
                        submission=submission,
                        file_path=file_path,
                        summary="Error calling LLM for this file.",
                        processing_error=str(e),
                        processed=False,
                        raw_response={"raw": str(e)},
                    )
                    continue

                # parse JSON
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
                    file_path=file_path,
                    summary=parsed.get("summary", "") if isinstance(parsed, dict) else "",
                    issues=parsed.get("issues", []) if isinstance(parsed, dict) else [],
                    suggestions=parsed.get("suggestions", [])
                    if isinstance(parsed, dict)
                    else [],
                    tests_suggestions=parsed.get("tests_suggestions", "")
                    if isinstance(parsed, dict)
                    else "",
                    quality_score=parsed.get("quality_score", None)
                    if isinstance(parsed, dict)
                    else None,
                    raw_response={"raw": raw},
                    processed=True,
                )
                created_reviews.append(review)

            messages.info(
                request,
                f"Created {len(created_reviews)} file-level reviews from ZIP project.",
            )
            # go to project page listing all file reviews
            return redirect(
                reverse("reviews:project_detail", kwargs={"submission_id": submission.id})
            )

        # ---------- CASE 2: SINGLE FILE OR ONLY TEXT ----------
        # if there is an upload but not zip → treat as one file
        code = base_code

        if upload:
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                messages.error(
                    request,
                    f"Uploaded file is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                messages.error(
                    request,
                    "Detected an image file. Please upload a text code file.",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            name_lower = upload.name.lower()
            if not any(name_lower.endswith(ext) for ext in ALLOWED_CODE_EXT):
                messages.warning(
                    request,
                    "Uploaded file extension is unusual for code. "
                    "We will try to read it, but prefer .py/.js/.java/.txt/.md.",
                )

            try:
                file_content = upload.read().decode("utf-8", errors="ignore")
            except Exception:
                messages.error(request, "Unable to read uploaded file as text.")
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            if len(code) + len(file_content) > settings.MAX_CODE_CHARS:
                messages.error(
                    request,
                    "Combined code too long. Please shorten the input.",
                )
                submission.delete()
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            code = code + "\n\n" + file_content

        if not code.strip():
            messages.error(
                request, "Please paste code or upload a small code file."
            )
            submission.delete()
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        # single review flow
        prompt = build_review_prompt(code, language)
        try:
            raw = call_llm(prompt)
        except Exception as e:
            messages.error(request, f"LLM request failed: {e}")
            submission.delete()
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

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
            suggestions=parsed.get("suggestions", [])
            if isinstance(parsed, dict)
            else [],
            tests_suggestions=parsed.get("tests_suggestions", "")
            if isinstance(parsed, dict)
            else "",
            quality_score=parsed.get("quality_score", None)
            if isinstance(parsed, dict)
            else None,
            raw_response={"raw": raw},
            processed=True,
        )

        return redirect(reverse("reviews:detail", kwargs={"pk": review.id}))

    # GET path
    return render(
        request,
        "reviews/index.html",
        {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
    )


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
    return render(
        request,
        "reviews/result.html",
        {"review": review, "pretty_raw": pretty_raw},
    )


def project_detail(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    reviews = submission.reviews.all().order_by("file_path", "created_at")
    return render(
        request,
        "reviews/project_detail.html",
        {"submission": submission, "reviews": reviews},
    )


def history(request):
    subs = Submission.objects.order_by("-created_at")[:50]
    return render(request, "reviews/history.html", {"subs": subs})
