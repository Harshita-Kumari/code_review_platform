from diff_match_patch import diff_match_patch
from difflib import unified_diff

def create_diff(original: str, suggested: str) -> str:
    dmp = diff_match_patch()
    diffs = dmp.diff_main(original, suggested)
    dmp.diff_cleanupSemantic(diffs)
    patch = dmp.patch_toText(dmp.patch_make(original, suggested))
    return patch

def unified_diff_text(orig_text: str, new_text: str, filename="file"):
    orig_lines = orig_text.splitlines()
    new_lines = new_text.splitlines()
    return "\n".join(unified_diff(orig_lines, new_lines, fromfile=filename, tofile=filename + ".suggested", lineterm=""))
