"""OpenAI-compatible vision model client used by PDF2MD."""

from __future__ import annotations

import base64
import io
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

import requests
from PIL import Image


class VLMError(RuntimeError):
    pass


class _RetryableVLMError(VLMError):
    pass


def normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        )
    if isinstance(content, dict):
        return str(content.get("text", content))
    return str(content)


def extract_json_value(text: str) -> Any:
    decoder = json.JSONDecoder()
    candidates = []
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            candidates.append(value)
    arrays = [candidate for candidate in candidates if isinstance(candidate, list)]
    if arrays:
        return arrays[-1]
    if not candidates:
        raise ValueError("No JSON object or array found in VLM response")
    return candidates[-1]


def encode_image(path: Path, max_size: int = 1024) -> str:
    image = Image.open(path)
    width, height = image.size
    if max(width, height) > max_size:
        ratio = max_size / max(width, height)
        image = image.resize((int(width * ratio), int(height * ratio)), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


class VLMClient:
    def __init__(
        self,
        *,
        model: str,
        api_base: str,
        api_key: str,
        enable_thinking: bool | None = None,
        max_attempts: int = 3,
        backoff_seconds: float = 1.0,
        session: Any = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.enable_thinking = enable_thinking
        self.max_attempts = max(1, int(max_attempts))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self.session = session or requests
        self.sleep = sleep
        self.usage = {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._usage_lock = threading.Lock()

    def _payload(self, img_b64: str, prompt: str, max_tokens: int) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": max_tokens,
        }
        if self.enable_thinking is not None:
            payload["enable_thinking"] = self.enable_thinking
        return payload

    def _request_once(self, img_b64: str, prompt: str, max_tokens: int, timeout: int) -> str:
        response = self.session.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=self._payload(img_b64, prompt, max_tokens),
            timeout=timeout,
        )
        status = int(getattr(response, "status_code", 200))
        if status == 429 or status >= 500:
            raise _RetryableVLMError(f"VLM API returned HTTP {status}")
        if status >= 400:
            raise VLMError(f"VLM API returned HTTP {status}: {response.text[:500]}")
        data = response.json()
        message = data["choices"][0]["message"]
        content = normalize_content(message.get("content", "")).strip()
        usage = data.get("usage") or {}
        with self._usage_lock:
            self.usage["calls"] += 1
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                self.usage[key] += int(usage.get(key, 0) or 0)
        if not content:
            raise _RetryableVLMError("VLM returned empty content")
        return content

    def _with_retries(self, operation: Callable[[], Any], context: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
            except (requests.RequestException, _RetryableVLMError, ValueError, KeyError, TypeError) as error:
                last_error = error
                if attempt >= self.max_attempts:
                    break
                self.sleep(self.backoff_seconds * (2 ** (attempt - 1)))
        raise VLMError(f"{context} failed after {self.max_attempts} attempt(s): {last_error}") from last_error

    def analyze_b64(self, img_b64: str, prompt: str, *, max_tokens: int = 300, timeout: int = 90) -> str:
        return self._with_retries(
            lambda: self._request_once(img_b64, prompt, max_tokens, timeout),
            "VLM request",
        )

    def analyze_image(
        self,
        path: Path,
        prompt: str,
        *,
        max_tokens: int = 300,
        timeout: int = 90,
    ) -> str:
        return self.analyze_b64(
            encode_image(Path(path)),
            prompt,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def analyze_json_array(
        self,
        path: Path,
        prompt: str,
        *,
        max_tokens: int = 4000,
        timeout: int = 180,
    ) -> list[dict[str, Any]]:
        img_b64 = encode_image(Path(path))

        def operation() -> list[dict[str, Any]]:
            text = self._request_once(img_b64, prompt, max_tokens, timeout)
            value = extract_json_value(text)
            if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                raise ValueError("Expected a JSON array of objects")
            if not value:
                raise ValueError("Expected at least one JSON object")
            required = {"fig_type", "data_type", "content"}
            for index, item in enumerate(value):
                missing = required.difference(item)
                if missing:
                    raise ValueError(f"JSON item {index} is missing: {sorted(missing)}")
            return value

        return self._with_retries(operation, "VLM JSON extraction")

    def snapshot_usage(self) -> dict[str, int]:
        with self._usage_lock:
            return dict(self.usage)
