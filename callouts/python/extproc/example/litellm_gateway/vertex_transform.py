# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""OpenAI <-> Vertex AI request and response body transformations.

LiteLLM's public SDK exposes provider detection (`get_llm_provider`) but does
not have a stable public "transpile only, do not call" API. We use the
provider-specific transformer modules where possible and fall back to a manual
transformation for the OpenAI chat-completions <-> Vertex generateContent shape
when LiteLLM's internals shift.
"""

from typing import Any

# Vertex AI generateContent endpoint suffix.
_VERTEX_GENERATE = ":generateContent"
# Streaming uses ?alt=sse so Vertex emits Server-Sent Events instead of the
# default chunked-JSON-array format.
_VERTEX_STREAM = ":streamGenerateContent?alt=sse"

# Non-Gemini Model Garden models use Vertex AI's OpenAI-compatible endpoint.
# Maps the bare model name (from the request) to the publisher/model_id
# format that the openapi endpoint requires.
_OPENAI_COMPAT_MODEL_IDS: dict[str, str] = {
    "llama-3.3-70b": "meta/llama-3.3-70b-instruct-maas",
}

def is_gemini_model(model: str) -> bool:
    """Returns True if this model uses the Vertex generateContent API."""
    bare = model.split("/", 1)[1] if "/" in model else model
    return bare.lower().startswith("gemini")


def build_vertex_path(project: str, region: str, model: str, *, stream: bool = False) -> str:
    """Construct the Vertex AI URL path for a Gemini model.

    Only call this for Gemini models — non-Gemini models use
    build_openai_compat_path() and the OpenAI-compatible endpoint.
    """
    bare_model = model.split("/", 1)[1] if "/" in model else model
    suffix = _VERTEX_STREAM if stream else _VERTEX_GENERATE
    return (
        f"/v1/projects/{project}/locations/{region}"
        f"/publishers/google/models/{bare_model}{suffix}"
    )


def build_openai_compat_path(project: str, region: str) -> str:
    """Construct the Vertex AI OpenAI-compatible chat completions path."""
    return f"/v1/projects/{project}/locations/{region}/endpoints/openapi/chat/completions"


def resolve_openai_compat_model(bare_model: str, full_model: str) -> str:
    """Map a bare model name to the Vertex AI publisher/model_id format.

    Falls back to the full model string (e.g. 'mistralai/mistral-small-2503@001')
    when no explicit mapping exists, so the publisher prefix passes through.
    """
    return _OPENAI_COMPAT_MODEL_IDS.get(bare_model, full_model)


def transform_vertex_sse_chunk_to_openai(
    vertex_chunk: dict[str, Any],
    *,
    chat_id: str,
    created: int,
    model: str,
    role_emitted: bool,
) -> tuple[dict[str, Any], bool]:
    """Transform a single Vertex streamGenerateContent SSE chunk to OpenAI chunk.

    Returns the OpenAI chunk dict and a flag indicating whether the role delta
    was emitted on this chunk (so callers can stop emitting it on subsequent
    chunks).
    """
    candidates = vertex_chunk.get("candidates") or []
    choices: list[dict[str, Any]] = []
    role_emitted_now = role_emitted
    for i, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            continue
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        raw_finish = cand.get("finishReason")
        finish_reason = _map_finish_reason(raw_finish) if raw_finish else None
        delta: dict[str, Any] = {}
        if not role_emitted_now:
            delta["role"] = "assistant"
            role_emitted_now = True
        if text:
            delta["content"] = text
        choices.append({
            "index": i,
            "delta": delta,
            "finish_reason": finish_reason,
        })
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": choices,
    }
    return chunk, role_emitted_now


def transform_openai_to_vertex_request(openai_body: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAI chat-completions body to Vertex generateContent format.

    Maps `messages[]` -> `contents[]` (system messages collapse into
    `systemInstruction`), and forwards generation parameters into
    `generationConfig`.
    """
    messages = openai_body.get("messages") or []
    contents: list[dict[str, Any]] = []
    system_parts: list[dict[str, Any]] = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "user")
        content = msg.get("content", "")
        text = content if isinstance(content, str) else _flatten_parts(content)
        if role == "system":
            system_parts.append({"text": text})
            continue
        vertex_role = "model" if role == "assistant" else "user"
        contents.append({"role": vertex_role, "parts": [{"text": text}]})

    vertex: dict[str, Any] = {"contents": contents}
    if system_parts:
        vertex["systemInstruction"] = {"parts": system_parts}

    gen_cfg: dict[str, Any] = {}
    for src, dst in (
        ("temperature", "temperature"),
        ("top_p", "topP"),
        ("top_k", "topK"),
        ("max_tokens", "maxOutputTokens"),
        ("max_completion_tokens", "maxOutputTokens"),
        ("stop", "stopSequences"),
        ("presence_penalty", "presencePenalty"),
        ("frequency_penalty", "frequencyPenalty"),
        ("candidate_count", "candidateCount"),
    ):
        if src in openai_body and openai_body[src] is not None:
            gen_cfg[dst] = openai_body[src]
    if gen_cfg:
        vertex["generationConfig"] = gen_cfg
    return vertex


def transform_vertex_to_openai_response(
    vertex_body: dict[str, Any],
    *,
    model: str,
    provider: str,
) -> dict[str, Any]:
    """Convert a Vertex generateContent response to OpenAI chat-completions format."""
    candidates = vertex_body.get("candidates") or []
    choices: list[dict[str, Any]] = []
    for i, cand in enumerate(candidates):
        if not isinstance(cand, dict):
            continue
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        finish_reason = _map_finish_reason(cand.get("finishReason", ""))
        choices.append({
            "index": i,
            "message": {"role": "assistant", "content": text},
            "finish_reason": finish_reason,
        })

    usage = vertex_body.get("usageMetadata") or {}
    return {
        "id": vertex_body.get("responseId", ""),
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": choices,
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
        "x_provider": provider,
    }


def _flatten_parts(content: Any) -> str:
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(item.get("text", ""))
        return "".join(chunks)
    return ""


_FINISH_REASON_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "BLOCKLIST": "content_filter",
    "PROHIBITED_CONTENT": "content_filter",
}


def _map_finish_reason(vertex_reason: str) -> str:
    return _FINISH_REASON_MAP.get(vertex_reason, "stop")
