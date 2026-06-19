"""OpenAI Vision client for one-call-per-claim review."""

from __future__ import annotations

import json
import os
import time
from typing import Any

from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT, build_user_prompt
from schemas import output_json_schema_for_api
from utils import load_image_data_urls


FALLBACK_OUTPUT = {
    "evidence_standard_met": False,
    "evidence_standard_met_reason": "Automated review failed or no usable model response was available.",
    "risk_flags": ["manual_review_required"],
    "issue_type": "unknown",
    "object_part": "unknown",
    "claim_status": "not_enough_information",
    "claim_status_justification": "Manual review is required because the automated image review did not complete.",
    "supporting_image_ids": ["none"],
    "valid_image": False,
    "severity": "unknown",
}


REQUEST_TIMEOUT_SECONDS = 75


def _load_openai_client():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    return OpenAI(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS, max_retries=0)


def _parse_response_text(text: str) -> dict[str, Any]:
    return json.loads(text)


def _extract_response_text(response: Any) -> str:
    if hasattr(response, "choices"):
        return response.choices[0].message.content or ""
    if hasattr(response, "output_text"):
        return response.output_text or ""
    raise ValueError("Unsupported OpenAI response object")


def _call_chat_completions(client: Any, messages: list[dict[str, Any]], model: str) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format=output_json_schema_for_api(),
        messages=messages,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    return _parse_response_text(_extract_response_text(response))


def review_claim_with_images(
    claim_row: Any,
    image_paths: list[str],
    image_ids: list[str],
    user_history: list[dict[str, Any]],
    evidence_requirements: list[dict[str, Any]],
    model: str = "gpt-4o",
) -> dict[str, Any]:
    """Send one claim plus its images to OpenAI Vision and return raw JSON."""
    client = _load_openai_client()
    if client is None:
        fallback = dict(FALLBACK_OUTPUT)
        fallback["evidence_standard_met_reason"] = (
            "OPENAI_API_KEY or openai package is unavailable; returning safe fallback."
        )
        return fallback

    image_payloads = load_image_data_urls(image_paths)
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": build_user_prompt(
                claim_row=claim_row,
                image_ids=image_ids,
                user_history=user_history,
                evidence_requirements=evidence_requirements,
            ),
        }
    ]
    for image in image_payloads:
        if image.get("data_url"):
            content.append(
                {
                    "type": "text",
                    "text": f"Image ID: {image['image_id']} | path: {image['path']}",
                }
            )
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image["data_url"], "detail": "high"},
                }
            )
        else:
            content.append(
                {
                    "type": "text",
                    "text": (
                        f"Image ID: {image['image_id']} could not be loaded "
                        f"from {image['path']} ({image['load_error']})."
                    ),
                }
            )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return _call_chat_completions(client, messages, model)
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()
            retryable = any(
                marker in error_text
                for marker in [
                    "rate limit",
                    "timeout",
                    "temporarily",
                    "server error",
                    "json",
                    "connection",
                    "timed out",
                    "readtimeout",
                    "apittimeout",
                    "429",
                    "500",
                    "502",
                    "503",
                    "504",
                ]
            )
            if attempt == 2 or not retryable:
                break
            time.sleep(2 * (attempt + 1))

    fallback = dict(FALLBACK_OUTPUT)
    fallback["evidence_standard_met_reason"] = (
        f"Automated review failed after limited retries: {type(last_error).__name__}."
    )
    return fallback
