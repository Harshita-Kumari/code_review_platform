# reviews/llm_client.py
import json
import requests
from django.conf import settings

def call_openai_chat(prompt: str, model=None, max_tokens=1200, temperature=0.0):
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OpenAI API key not configured.")
    url = settings.OPENAI_API_URL
    model = model or settings.OPENAI_DEFAULT_MODEL
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful code reviewer."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    if "choices" in data and data["choices"]:
        msg = data["choices"][0].get("message", {})
        if isinstance(msg, dict):
            return msg.get("content") or ""
    return json.dumps(data)


def call_anthropic_messages(prompt: str, model=None, max_tokens=1200, temperature=0.0):
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        raise RuntimeError("Anthropic API key not configured.")
    url = settings.ANTHROPIC_API_URL
    model = model or settings.ANTHROPIC_DEFAULT_MODEL
    headers = {"x-api-key": api_key, "content-type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": temperature}
    r = requests.post(url, json=payload, headers=headers, timeout=120)
    r.raise_for_status()
    d = r.json()
    if isinstance(d, dict):
        if "content" in d and isinstance(d["content"], list):
            return "".join(item.get("text", "") for item in d["content"] if isinstance(item, dict))
        if "completion" in d:
            return d["completion"]
    return json.dumps(d)


def call_llm(prompt: str, provider=None, **kwargs):
    provider = provider or settings.LLM_PROVIDER
    if provider == "anthropic":
        return call_anthropic_messages(prompt, **kwargs)
    else:
        return call_openai_chat(prompt, **kwargs)
