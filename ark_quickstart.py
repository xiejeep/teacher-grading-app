#!/usr/bin/env python3
"""Minimal Volcengine Ark Responses API client.

Reads ARK_API_KEY from the environment and calls:
https://ark.cn-beijing.volces.com/api/v3/responses
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "doubao-seed-2-0-pro-260215"


def build_payload(prompt: str, disable_thinking: bool) -> dict:
    payload: dict = {
        "model": ARK_MODEL,
        "input": prompt,
    }
    if disable_thinking:
        payload["thinking"] = {"type": "disabled"}
    return payload


def request_response(prompt: str, disable_thinking: bool = False) -> dict:
    api_key = os.getenv("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("ARK_API_KEY is not set")

    body = json.dumps(build_payload(prompt, disable_thinking), ensure_ascii=False).encode(
        "utf-8"
    )
    request = urllib.request.Request(
        f"{ARK_BASE_URL}/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ark API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to call Ark API: {exc.reason}") from exc


def extract_text(response: dict) -> str | None:
    output_text = response.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    chunks: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks).strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Call Volcengine Ark Responses API.")
    parser.add_argument("prompt", nargs="?", default="hello", help="Prompt to send.")
    parser.add_argument(
        "--disable-thinking",
        action="store_true",
        help="Send thinking={type: disabled}.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON response instead of extracted text.",
    )
    args = parser.parse_args()

    try:
        response = request_response(args.prompt, disable_thinking=args.disable_thinking)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(extract_text(response) or json.dumps(response, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
