def build_review_prompt(code: str, language: str) -> str:
    schema = '''{
  "summary": "<short summary>",
  "issues": [{"line": null, "severity": "low|medium|high", "message": "<text>", "type": "bug|style|security|performance|other"}],
  "suggestions": [{"description": "<text>", "patch": "<code or diff>", "lines": "<start-end or null>"}],
  "tests_suggestions": "<text>",
  "quality_score": 0
}'''
    return f"""You are an expert senior {language} engineer and code reviewer.
Return only valid JSON matching this schema (no extra commentary):
{schema}

CODE:
\"\"\"{code}\"\"\""""
