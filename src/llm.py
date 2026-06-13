"""LLM client for Dockerfile optimization suggestions."""

import json
import urllib.request
import urllib.error
import os


SYSTEM_PROMPT = """You are an expert Docker engineer optimizing Dockerfiles for size, speed, and security.

Given a Dockerfile analysis with issues, provide optimized code.

Rules:
- Provide the complete optimized Dockerfile
- Explain each change briefly
- Focus on: multi-stage builds, layer caching, security hardening, size reduction
- Use comments in the Dockerfile to explain optimizations
- Keep the same functionality
- Use best practices (non-root user, pinned versions, proper cleanup)

Output in markdown format with:
1. Summary of optimizations
2. Complete optimized Dockerfile
3. Explanation of each change"""


def optimize_dockerfile(
    analysis_prompt: str,
    ollama_url: str = "http://localhost:11434",
    model: str = "llama3.2",
) -> str:
    """Generate optimized Dockerfile suggestion."""
    user_prompt = f"""Optimize this Dockerfile:

{analysis_prompt}"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3},
    }

    try:
        req = urllib.request.Request(
            f"{ollama_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["message"]["content"].strip()
    except urllib.error.URLError:
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            return _optimize_openai(analysis_prompt, openai_key)
        raise ConnectionError(
            f"Cannot connect to Ollama at {ollama_url}. "
            "Start Ollama: ollama serve"
        )


def _optimize_openai(analysis_prompt: str, api_key: str) -> str:
    """Fallback to OpenAI."""
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Optimize this Dockerfile:\n\n{analysis_prompt}"},
        ],
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()


def check_ollama(ollama_url: str = "http://localhost:11434") -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request(f"{ollama_url}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False
