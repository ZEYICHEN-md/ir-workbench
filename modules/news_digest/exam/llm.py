"""可选的独立 LLM 调用。场次默认不依赖外网密钥；有密钥时裁判可走模型。

考生与裁判不得共用同一模型名（卷面锁定第 7 条）。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

CANDIDATE_MODEL_HINT = "skill-policy-interpreter"
DEFAULT_JUDGE_MODEL = "gpt-4.1-mini"
DEFAULT_EXAMINER_MODEL = "script-interpreter"


class LlmError(RuntimeError):
    pass


def available() -> dict[str, str]:
    """返回已配置的提供方。没有密钥时为空——考试仍可跑脚本考官 + 证据裁判。"""
    found: dict[str, str] = {}
    if os.environ.get("ANTHROPIC_API_KEY"):
        found["anthropic"] = os.environ.get("IR_EXAM_JUDGE_MODEL") or "claude-sonnet-4-5"
    if os.environ.get("OPENAI_API_KEY"):
        found["openai"] = os.environ.get("IR_EXAM_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL
    if os.environ.get("OPENROUTER_API_KEY"):
        found["openrouter"] = os.environ.get("IR_EXAM_JUDGE_MODEL") or "openai/gpt-4.1-mini"
    return found


def judge_model_name() -> str:
    providers = available()
    if "anthropic" in providers:
        return providers["anthropic"]
    if "openai" in providers:
        return providers["openai"]
    if "openrouter" in providers:
        return providers["openrouter"]
    return "evidence-rubric-program"


def candidate_model_name() -> str:
    # 考生本场是 SKILL 政策解释器，不是 LLM。即使之后接上 LLM，也必须与裁判不同名。
    override = (os.environ.get("IR_EXAM_CANDIDATE_MODEL") or "").strip()
    return override or CANDIDATE_MODEL_HINT


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int = 60) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise LlmError(str(error)) from error


def complete(system: str, user: str, *, role: str = "judge") -> str | None:
    """成功返回模型文本；无密钥或失败返回 None（调用方走证据裁判）。"""
    providers = available()
    if not providers:
        return None
    # 裁判优先用 Anthropic，避免与未来 OpenAI 考生撞车。
    if role == "judge" and "anthropic" in providers:
        return _anthropic(system, user, providers["anthropic"])
    if "openai" in providers:
        model = providers["openai"]
        if role == "judge" and model == candidate_model_name():
            model = DEFAULT_JUDGE_MODEL
        return _openai_compatible(
            "https://api.openai.com/v1/chat/completions",
            os.environ["OPENAI_API_KEY"],
            model,
            system,
            user,
        )
    if "openrouter" in providers:
        return _openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions",
            os.environ["OPENROUTER_API_KEY"],
            providers["openrouter"],
            system,
            user,
        )
    if "anthropic" in providers:
        return _anthropic(system, user, providers["anthropic"])
    return None


def _anthropic(system: str, user: str, model: str) -> str | None:
    try:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": model,
                "max_tokens": 1200,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            {
                "content-type": "application/json",
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
            },
        )
    except LlmError:
        return None
    blocks = data.get("content") or []
    texts = [block.get("text") for block in blocks if isinstance(block, dict)]
    joined = "\n".join(text for text in texts if text)
    return joined or None


def _openai_compatible(url: str, key: str, model: str, system: str, user: str) -> str | None:
    try:
        data = _post_json(
            url,
            {
                "model": model,
                "temperature": 0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            {
                "content-type": "application/json",
                "authorization": f"Bearer {key}",
            },
        )
    except LlmError:
        return None
    choices = data.get("choices") or []
    if not choices:
        return None
    return (choices[0].get("message") or {}).get("content")
