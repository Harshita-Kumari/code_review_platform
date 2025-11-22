# reviews/views.py
import json
import re
import imghdr
import zipfile
import io

import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages

from .forms import SubmissionForm
from .models import Submission, Review
from .prompts import build_review_prompt
from .llm_client import call_llm

ALLOWED_CODE_EXT = (".py", ".js", ".java", ".txt", ".md")


def _iter_zip_bytes(zip_bytes: bytes, per_file_limit: int):
    """
    Yield (file_path, text) for each code file inside a ZIP archive given as bytes.
    Only includes ALLOWED_CODE_EXT extensions.
    """
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = info.filename
        if not any(name.lower().endswith(ext) for ext in ALLOWED_CODE_EXT):
            continue
        try:
            file_bytes = zf.read(info)
            text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            continue
        text = text.strip()
        if not text:
            continue
        if len(text) > per_file_limit:
            text = text[:per_file_limit]
        yield name, text


def _download_github_repo_zip(repo_url: str) -> bytes:
    """
    Given a GitHub repo URL, download its ZIP (main/master or specific branch).
    Supports:
      - https://github.com/user/repo
      - https://github.com/user/repo/
      - https://github.com/user/repo.git
      - https://github.com/user/repo/tree/branch
    """
    url = repo_url.strip()
    if not url.startswith("http"):
        raise ValueError("Please enter a full GitHub URL starting with https://")
    if "github.com" not in url:
        raise ValueError("Only GitHub URLs from github.com are supported.")

    # strip .git if present
    if url.endswith(".git"):
        url = url[:-4]

    branch = "main"
    if "/tree/" in url:
        base, _, branch_part = url.partition("/tree/")
        base_url = base
        branch = branch_part.strip("/").split("/")[0] or "main"
    else:
        base_url = url

    def build_zip_url(br: str) -> str:
        return base_url.rstrip("/") + f"/archive/refs/heads/{br}.zip"

    try_order = [branch, "main", "master"]
    last_status = None

    for br in try_order:
        zip_url = build_zip_url(br)
        resp = requests.get(zip_url, timeout=60)
        last_status = resp.status_code
        if resp.status_code == 200:
            return resp.content

    raise ValueError(
        f"Could not download ZIP from GitHub. Last HTTP status: {last_status}."
    )


def index(request):
    form = SubmissionForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        title = form.cleaned_data["title"] or "Untitled review"
        language = form.cleaned_data["language"]
        base_code = form.cleaned_data["code"] or ""
        upload = request.FILES.get("upload")
        repo_url = form.cleaned_data.get("repo_url") or ""

        # prevent both upload and repo_url at same time
        if upload and repo_url:
            messages.error(
                request,
                "Please either upload a file/ZIP or enter a GitHub repository URL, not both.",
            )
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        if not upload and not repo_url and not base_code.strip():
            messages.error(
                request,
                "Please paste code, upload a file/ZIP, or enter a GitHub repository URL.",
            )
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        # create submission (represents this review request / project)
        submission = Submission.objects.create(
            title=title,
            language=language,
            code=base_code or "",
            user=request.user if request.user.is_authenticated else None,
        )

        # ===================== CASE 1: GITHUB REPO URL =====================
        if repo_url:
            try:
                zip_bytes = _download_github_repo_zip(repo_url)
            except ValueError as e:
                submission.delete()
                messages.error(request, str(e))
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            if len(zip_bytes) > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                submission.delete()
                messages.error(
                    request,
                    f"Downloaded repo ZIP is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            files = list(
                _iter_zip_bytes(zip_bytes, per_file_limit=settings.MAX_CODE_CHARS)
            )
            if not files:
                submission.delete()
                messages.error(
                    request,
                    "No readable .py/.js/.java/.txt/.md files found in the GitHub repository.",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            created_reviews = []

            for file_path, file_code in files:
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
                    Review.objects.create(
                        submission=submission,
                        file_path=file_path,
                        summary="Error calling LLM for this file.",
                        processing_error=str(e),
                        processed=False,
                        raw_response={"raw": str(e)},
                    )
                    continue

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
                f"Created {len(created_reviews)} file-level reviews from GitHub repo.",
            )
            return redirect(
                reverse(
                    "reviews:project_detail", kwargs={"submission_id": submission.id}
                )
            )

        # ===================== CASE 2: ZIP UPLOAD (per-file) =====================
        if upload and upload.name.lower().endswith(".zip"):
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                submission.delete()
                messages.error(
                    request,
                    f"Uploaded ZIP is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                submission.delete()
                messages.error(
                    request,
                    "Detected an image file. Please upload a real ZIP project or code file.",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            zip_bytes = upload.read()
            files = list(
                _iter_zip_bytes(zip_bytes, per_file_limit=settings.MAX_CODE_CHARS)
            )
            if not files:
                submission.delete()
                messages.error(
                    request,
                    "No readable .py/.js/.java/.txt/.md files found inside ZIP.",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            created_reviews = []
            for file_path, file_code in files:
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
                    Review.objects.create(
                        submission=submission,
                        file_path=file_path,
                        summary="Error calling LLM for this file.",
                        processing_error=str(e),
                        processed=False,
                        raw_response={"raw": str(e)},
                    )
                    continue

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
            return redirect(
                reverse(
                    "reviews:project_detail", kwargs={"submission_id": submission.id}
                )
            )

        # ===================== CASE 3: SINGLE FILE or PASTED TEXT =====================
        code = base_code

        if upload:
            if upload.size > settings.MAX_FILE_UPLOAD_MB * 1024 * 1024:
                submission.delete()
                messages.error(
                    request,
                    f"Uploaded file is too large (max {settings.MAX_FILE_UPLOAD_MB} MB).",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            head = upload.read(512)
            upload.seek(0)
            if imghdr.what(None, head) is not None:
                submission.delete()
                messages.error(
                    request,
                    "Detected an image file. Please upload a text code file.",
                )
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
                submission.delete()
                messages.error(request, "Unable to read uploaded file as text.")
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            if len(code) + len(file_content) > settings.MAX_CODE_CHARS:
                submission.delete()
                messages.error(
                    request,
                    "Combined code too long. Please shorten the input.",
                )
                return render(
                    request,
                    "reviews/index.html",
                    {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
                )

            code = code + "\n\n" + file_content

        if not code.strip():
            submission.delete()
            messages.error(
                request, "Please paste code or upload a small code file."
            )
            return render(
                request,
                "reviews/index.html",
                {"form": form, "max_file_mb": settings.MAX_FILE_UPLOAD_MB},
            )

        prompt = build_review_prompt(code, language)
        try:
            raw = call_llm(prompt)
        except Exception as e:
            submission.delete()
            messages.error(request, f"LLM request failed: {e}")
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

    # GET
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
    reviews_qs = submission.reviews.all().order_by("file_path", "created_at")

    # Build simple "tree-like" list: each item has depth based on folder nesting
    tree_items = []
    for r in reviews_qs:
        # If file_path is empty (single file review), give a friendly name
        raw_path = r.file_path or "Full code"
        # normalize
        path = raw_path.strip("/")
        depth = path.count("/")  # how deep in folders
        file_name = path.split("/")[-1]
        tree_items.append({
            "review": r,
            "path": path,
            "file_name": file_name,
            "depth": depth,
        })

    # Sort by path to group similar folders together
    tree_items.sort(key=lambda n: n["path"])

    return render(
        request,
        "reviews/project_detail.html",
        {
            "submission": submission,
            "reviews": reviews_qs,
            "tree_items": tree_items,
        },
    )



def history(request):
    subs = Submission.objects.order_by("-created_at")[:50]
    return render(request, "reviews/history.html", {"subs": subs})
