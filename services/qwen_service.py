"""Analyze an uploaded garbage image with DashScope Qwen3-VL."""

from http import HTTPStatus
import os
from pathlib import Path
import re

import dashscope
from requests.exceptions import Timeout


MODEL_NAME = "qwen3-vl-plus"
PROMPT = """
请分析图片中的主要垃圾物体。

请回答：
1. 物体是什么？
2. 它属于哪种垃圾类别？
3. 是否可回收？
4. 简单说明判断理由。
"""


class QwenConfigurationError(RuntimeError):
    pass


class QwenAPIError(RuntimeError):
    pass


class QwenTimeoutError(QwenAPIError):
    pass


def _redact(value, api_key: str) -> str:
    text = str(value).replace(api_key, "[REDACTED]")
    return re.sub(r"\bsk-[A-Za-z0-9_-]+\b", "[REDACTED]", text)


def analyze_image(image_path: str | Path) -> str:
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not api_key:
        raise QwenConfigurationError("DASHSCOPE_API_KEY is not configured")

    image_path = Path(image_path).resolve()
    if not image_path.is_file():
        raise FileNotFoundError(f"Image does not exist: {image_path}")

    messages = [{
        "role": "user",
        "content": [
            {"image": image_path.as_uri()},
            {"text": PROMPT},
        ],
    }]

    try:
        response = dashscope.MultiModalConversation.call(
            api_key=api_key,
            model=MODEL_NAME,
            messages=messages,
            stream=False,
            request_timeout=60,
        )
    except Timeout:
        raise QwenTimeoutError("The Qwen request timed out") from None
    except Exception as error:
        raise QwenAPIError(
            f"Qwen request failed: {_redact(error, api_key)}"
        ) from None

    status_code = getattr(response, "status_code", None)
    if status_code != HTTPStatus.OK:
        detail = _redact(
            f"Qwen request failed (HTTP {status_code}, "
            f"code {getattr(response, 'code', 'UnknownError')}): "
            f"{getattr(response, 'message', 'No response details')}",
            api_key,
        )
        if status_code in (HTTPStatus.REQUEST_TIMEOUT, HTTPStatus.GATEWAY_TIMEOUT):
            raise QwenTimeoutError(detail)
        raise QwenAPIError(detail)

    try:
        content = response.output.choices[0].message.content
        if isinstance(content, str):
            answer = content.strip()
        else:
            answer = "\n".join(
                part["text"] for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
    except (AttributeError, IndexError, KeyError, TypeError):
        raise QwenAPIError("Qwen returned an invalid response format") from None

    if not answer:
        raise QwenAPIError("Qwen returned an empty answer")
    return _redact(answer, api_key)
