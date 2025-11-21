# reviews/prompts.py
def build_review_prompt(code: str, language: str) -> str:
    schema = '''{
  "summary": "<short summary>",
  "issues": [{"line": null, "severity": "low|medium|high", "message": "<text>", "type": "bug|style|security|performance|other"}],
  "suggestions": [{"description": "<text>", "patch": "<code or diff>", "lines": "<start-end or null>"}],
  "tests_suggestions": "<text>",
  "quality_score": 0
}'''
    return f"""You are an expert senior {language} engineer and code reviewer.
Return ONLY valid JSON that exactly matches this schema (no extra text, no explanation). If you cannot parse, return an empty JSON with 'raw' field.
Schema:
{schema}

Now review the following CODE and output JSON exactly:

CODE:
\"\"\"{code}\"\"\""""
