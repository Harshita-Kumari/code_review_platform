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


ALLOWED_CODE_EXT = (".py", ".js", ".java", ".txt", ".md")


def _read_zip_as_code(upload_file, max_chars):
    """
    Read a .zip upload and return concatenated code (str).
    Only includes ALLOWED_CODE_EXT files.
    Adds a header '# FILE: path' before each file.
    Truncates if total length > max_chars.
    """
    data = upload_file.read()
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("Uploaded ZIP file is invalid or corrupted.")

    pieces = []
    total_len = 0
    file_count = 0

    for info in zf.infolist():
        if info.is_dir():
            continue

        name = info.filename
        if not any(name.lower().endswith(ext) for ext in ALLOWED_CODE_EXT):
            # skip non-code files (images, binaries, etc.)
            continue

        try:
            file_bytes = zf.read(info)
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            # skip unreadable files
            continue

        if not text.strip():
            continue

        header = f"\n\n# FILE: {name}\n"
        chunk = header + text
        chunk_len = len(chunk)

        if total_len + chunk_len > max_chars:
            # take only part of this chunk
            remaining = max_chars - total_len
            if remaining > 0:
                pieces.append(chunk[:remaining])
                total_len += remaining
            # reached limit
            break

        pieces.append(chunk)
        total_len += chunk_len
        file_count += 1

        if total_len >= max_chars:
            break

    if not pieces:
        raise ValueError("No readable code files found inside ZIP.")

    code = "".join(pieces)
    return code, file_count, total_len


def index(request):
    form = SubmissionForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"] or "Untitled review"
        language = form.cleaned_data["language"]
        code = form.cleaned_data["code"] or ""
        upload = request.FILES.get("upload")

        # ---- handle upload (single file OR zip project) ----
        if upload:
            # file size limit (in MB)
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                messages.error(
                    request,
                    f"Uploaded file is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            # read small header to detect images
            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                messages.error(
                    request,
                    "Detected an image file. Please upload a code file or a ZIP project, not an image.",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            # If it's a ZIP: treat as project folder
            name_lower = upload.name.lower()
            if name_lower.endswith(".zip"):
                try:
                    project_code, file_count, total_len = _read_zip_as_code(
                        upload, settings.MAX_CODE_CHARS
                    )
                except ValueError as e:
                    messages.error(request, str(e))
                    return render(
                        request,
                        "reviews/index.html",
                        {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                    )

                # merge pasted code (if any) + project code
                combined = code + "\n\n" + project_code if code else project_code
                if len(combined) > settings.MAX_CODE_CHARS:
                    combined = combined[: settings.MAX_CODE_CHARS]
                    messages.warning(
                        request,
                        "Project is large; code was truncated to fit the review limit.",
                    )

                code = combined
                messages.info(
                    request,
                    f"Loaded {file_count} files from ZIP project for review.",
                )

            else:
                # normal single-text-file path
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
                    return render(
                        request,
                        "reviews/index.html",
                        {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                    )

                if len(code) + len(file_content) > settings.MAX_CODE_CHARS:
                    messages.error(
                        request,
                        "Combined code too long. Please shorten the input or project.",
                    )
                    return render(
                        request,
                        "reviews/index.html",
                        {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                    )

                code = code + "\n\n" + file_content

        # ---- final validation ----
        if not code.strip():
            messages.error(
                request, "Please paste code or upload a code file / ZIP project."
            )
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        # ---- save submission ----
        submission = Submission.objects.create(
            title=title,
            language=language,
            code=code,
            user=request.user if request.user.is_authenticated else None,
        )

        # ---- call LLM ----
        prompt = build_review_prompt(code, language)
        try:
            raw = call_llm(prompt)
        except Exception as e:
            messages.error(request, f"LLM request failed: {e}")
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        # ---- parse LLM JSON ----
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
    return render(request, "reviews/result.html", {"review": review, "pretty_raw": pretty_raw})


def history(request):
    subs = Submission.objects.order_by("-created_at")[:50]
    return render(request, "reviews/history.html", {"subs": subs})
