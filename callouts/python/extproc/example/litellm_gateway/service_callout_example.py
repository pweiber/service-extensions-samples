# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""LiteLLM Gateway callout — transpiles OpenAI requests to Vertex AI in-process.

The Service Extensions callout takes ownership of the work that previously ran
in a separate LiteLLM Cloud Run middleware:

  * provider detection (via `litellm.get_llm_provider`)
  * OpenAI -> Vertex request body transformation
  * `:path`, `:authority`, and `Authorization` header rewriting so the LB can
    forward straight to `*-aiplatform.googleapis.com` (the LB backend)
  * Vertex -> OpenAI response body transformation

Per-stream state (matched keywords, resolved model/provider) is attached to the
gRPC ServicerContext so it survives across REQUEST_HEADERS, REQUEST_BODY,
RESPONSE_HEADERS, and RESPONSE_BODY phases for a single request.
"""

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from grpc import ServicerContext

from envoy.config.core.v3.base_pb2 import HeaderValue, HeaderValueOption
from envoy.extensions.filters.http.ext_proc.v3.processing_mode_pb2 import ProcessingMode
from envoy.service.ext_proc.v3 import external_processor_pb2 as service_pb2
from envoy.type.v3.http_status_pb2 import StatusCode

from extproc.service import callout_server
from extproc.service import callout_tools

from extproc.example.litellm_gateway.vertex_auth import fetch_vertex_token
from extproc.example.litellm_gateway.vertex_transform import (
    build_openai_compat_path,
    build_vertex_path,
    is_gemini_model,
    resolve_openai_compat_model,
    transform_openai_to_vertex_request,
    transform_vertex_sse_chunk_to_openai,
    transform_vertex_to_openai_response,
)

try:
    import litellm  # type: ignore
except ImportError:  # pragma: no cover - exercised only in environments without litellm
    litellm = None


# Header names emitted/consumed by the callout.
HEADER_TARGET_PROVIDER = "x-v2-target-provider"
HEADER_SEC_KEYWORD = "x-sec-keyword"
HEADER_LITELLM_POLICY = "x-litellm-policy"
HEADER_LITELLM_ROUTED = "x-litellm-routed"
POLICY_ALLOWED = "allowed"
DEFAULT_PROVIDER = "vertex_ai"

# OpenAI-compatible paths the callout inspects. Anything else is a no-op.
LLM_ENDPOINTS = frozenset({
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/embeddings",
    "/v1/models",
    "/chat/completions",
    "/completions",
    "/embeddings",
})


@dataclass
class _StreamState:
    matched_keywords: list[str] = field(default_factory=list)
    model: str = ""
    provider: str = ""
    is_llm: bool = False
    is_streaming: bool = False
    # False for non-Gemini models: Vertex returns OpenAI format directly.
    needs_response_transform: bool = True
    # Non-streaming response: buffer all chunks and transform on end_of_stream.
    body_buffer: bytearray = field(default_factory=bytearray)
    # Streaming response: buffer partial SSE events that span chunk boundaries.
    sse_buffer: str = ""
    # Streaming response: per-stream chat completion id and creation timestamp.
    chat_id: str = ""
    created_ts: int = 0
    # Streaming response: whether the assistant role delta has been emitted.
    role_emitted: bool = False


def _state(context: ServicerContext) -> _StreamState:
    """Return per-stream state attached to the gRPC context, creating it on first access."""
    state = getattr(context, "_litellm_state", None)
    if state is None:
        state = _StreamState()
        context._litellm_state = state
    return state


class LiteLLMGatewayCallout(callout_server.CalloutServer):
    """Ext_proc callout that transpiles OpenAI -> Vertex AI in flight."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sec_keywords = _parse_csv_lower(os.getenv("SEC_KEYWORDS", ""))
        self.allowed_models = _parse_csv_set(os.getenv("ALLOWED_MODELS", ""))
        self.gcp_project = os.getenv("GCP_PROJECT_ID", "")
        self.gcp_region = os.getenv("GCP_REGION", "us-central1")

        if self.sec_keywords:
            logging.info("SEC_KEYWORDS enabled: %s", self.sec_keywords)
        if self.allowed_models:
            logging.info("ALLOWED_MODELS enabled: %s", sorted(self.allowed_models))
        if not self.gcp_project:
            logging.warning(
                "GCP_PROJECT_ID is unset. Vertex paths will be malformed until set.")

    def process(self, callout, context):
        """Inject mode_override=STREAMED on the ProcessingResponse for SSE requests.

        The base class wraps on_request_body's BodyResponse in ProcessingResponse
        but has no hook for mode_override.  We add it here after the base class
        produces the response, using ProcessingResponse.mode_override (field 8)
        which is present in all supported proto versions — unlike
        CommonResponse.mode_override (field 5) which is absent in older packages.
        """
        resp = super().process(callout, context)
        if callout.HasField('request_body') and not resp.HasField('immediate_response'):
            state = _state(context)
            if state.is_streaming:
                stream_mode = ProcessingMode()
                stream_mode.response_body_mode = ProcessingMode.STREAMED
                resp.mode_override.CopyFrom(stream_mode)
        return resp

    # ------------------------------------------------------------------ phases

    def on_request_headers(
        self,
        headers: service_pb2.HttpHeaders,
        context: ServicerContext,
    ) -> service_pb2.ProcessingResponse | None:
        path, method = "", ""
        for h in headers.headers.headers:
            if h.key == ":path":
                path = h.raw_value.decode("utf-8")
            elif h.key == ":method":
                method = h.raw_value.decode("utf-8")
        logging.info("Request %s %s", method, path)

        if path not in LLM_ENDPOINTS:
            return None

        state = _state(context)
        state.is_llm = True

        resp = service_pb2.ProcessingResponse()
        resp.request_headers.response.header_mutation.set_headers.append(
            HeaderValueOption(
                header=HeaderValue(key=HEADER_LITELLM_ROUTED, raw_value=b"true")))

        if method != "GET":
            mode = ProcessingMode()
            mode.request_body_mode = ProcessingMode.BUFFERED
            mode.response_header_mode = ProcessingMode.SEND
            # Default to BUFFERED so GCLB accumulates the full Vertex response
            # before invoking the callout — avoids the empty-body issue seen
            # with STREAMED mode on GCLB Traffic Extensions.  For streaming
            # (SSE) requests on_request_body upgrades this to STREAMED.
            mode.response_body_mode = ProcessingMode.BUFFERED
            resp.mode_override.CopyFrom(mode)
        return resp

    def on_request_body(
        self,
        body: service_pb2.HttpBody,
        context: ServicerContext,
    ) -> service_pb2.BodyResponse | service_pb2.ImmediateResponse | None:
        state = _state(context)
        if not state.is_llm:
            return None

        raw = body.body
        if not raw:
            return service_pb2.BodyResponse()

        try:
            req_map = json.loads(raw)
        except json.JSONDecodeError as e:
            logging.warning("Invalid JSON body: %s", e)
            return callout_tools.header_immediate_response(StatusCode.BadRequest)

        model = req_map.get("model") or ""
        if not isinstance(model, str):
            model = ""

        if self.allowed_models and model not in self.allowed_models:
            logging.warning("Rejected disallowed model: %r", model)
            return callout_tools.header_immediate_response(StatusCode.Forbidden)

        provider = _resolve_provider(model)
        state.model = model
        state.provider = provider
        state.is_streaming = bool(req_map.get("stream"))
        if state.is_streaming:
            state.chat_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            state.created_ts = int(time.time())

        state.matched_keywords = self._detect_keywords(req_map)
        if state.matched_keywords:
            logging.info("SEC keywords detected: %s", state.matched_keywords)

        messages = req_map.get("messages") or []
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        if isinstance(last_user, str):
            logging.info("Input: %s", last_user[:200])

        try:
            token = fetch_vertex_token()
        except Exception:
            logging.exception("Vertex AI token fetch failed")
            return callout_tools.header_immediate_response(
                StatusCode.InternalServerError)

        vertex_authority = f"{self.gcp_region}-aiplatform.googleapis.com"
        bare_model = model.split("/", 1)[1] if "/" in model else model

        if is_gemini_model(model):
            # Gemini: transform OpenAI → generateContent format.
            try:
                vertex_body = transform_openai_to_vertex_request(req_map)
            except Exception:
                logging.exception("Body transformation failed")
                return callout_tools.header_immediate_response(
                    StatusCode.InternalServerError)
            vertex_path = build_vertex_path(
                self.gcp_project, self.gcp_region, model, stream=state.is_streaming)
            new_body = json.dumps(vertex_body).encode("utf-8")
            state.needs_response_transform = True
        else:
            # Non-Gemini Model Garden models: use Vertex AI's OpenAI-compatible
            # endpoint — no body transform needed.
            vertex_model_id = resolve_openai_compat_model(bare_model, model)
            compat_body = dict(req_map)
            compat_body["model"] = vertex_model_id
            vertex_path = build_openai_compat_path(self.gcp_project, self.gcp_region)
            new_body = json.dumps(compat_body).encode("utf-8")
            state.needs_response_transform = False

        logging.info(
            "Routing to %s%s (streaming=%s) %s=%s",
            vertex_authority, vertex_path, state.is_streaming,
            HEADER_TARGET_PROVIDER, provider,
        )
        body_resp = service_pb2.BodyResponse()
        body_resp.response.body_mutation.body = new_body

        # For streaming, mode upgrade to STREAMED happens in process() override
        # below — on_request_body must return BodyResponse for the base class.

        # The original Content-Length came from the OpenAI body — overwrite to
        # match the transformed Vertex body or Envoy will reject the mutation.
        rewrites: list[tuple[str, str]] = [
            (":path", vertex_path),
            (":authority", vertex_authority),
            ("host", vertex_authority),
            ("authorization", f"Bearer {token}"),
            ("content-type", "application/json"),
            ("content-length", str(len(new_body))),
            # Prevent Vertex from returning a gzip-compressed body — the callout
            # must parse the response as JSON and cannot decompress on the fly.
            ("accept-encoding", "identity"),
            (HEADER_TARGET_PROVIDER, provider),
            (HEADER_LITELLM_POLICY, POLICY_ALLOWED),
        ]
        if state.matched_keywords:
            rewrites.append(
                (HEADER_SEC_KEYWORD, ",".join(state.matched_keywords)))

        for k, v in rewrites:
            body_resp.response.header_mutation.set_headers.append(
                HeaderValueOption(
                    header=HeaderValue(key=k, raw_value=v.encode("utf-8")),
                    # Replace the existing header rather than appending — we're
                    # overwriting :path, :authority, content-length, etc.
                    append_action=HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
                ))

        # Re-evaluate routing now that :path / :authority point at Vertex.
        body_resp.response.clear_route_cache = True
        return body_resp

    def on_response_headers(
        self,
        headers: service_pb2.HttpHeaders,
        context: ServicerContext,
    ) -> service_pb2.HeadersResponse | None:
        state = _state(context)
        if not state.is_llm:
            return service_pb2.HeadersResponse()

        status = ""
        for h in headers.headers.headers:
            if h.key == ":status":
                status = h.raw_value.decode("utf-8", errors="replace")
                break
        logging.info("Vertex response status: %s", status)

        resp = service_pb2.HeadersResponse()
        # Vertex's Content-Length will be wrong after our body transform — drop
        # it so Envoy switches to chunked transfer encoding for the response.
        resp.response.header_mutation.remove_headers.append("content-length")
        if state.matched_keywords:
            resp.response.header_mutation.set_headers.append(
                HeaderValueOption(
                    header=HeaderValue(
                        key=HEADER_SEC_KEYWORD,
                        raw_value=",".join(state.matched_keywords).encode("utf-8"),
                    ),
                    append_action=HeaderValueOption.OVERWRITE_IF_EXISTS_OR_ADD,
                ))
        return resp

    def on_response_body(
        self,
        body: service_pb2.HttpBody,
        context: ServicerContext,
    ) -> service_pb2.BodyResponse | None:
        state = _state(context)
        if not state.is_llm:
            return None
        if state.is_streaming:
            return self._handle_streaming_chunk(state, body.body or b"",
                                                bool(body.end_of_stream))
        return self._handle_buffered_chunk(state, body.body or b"",
                                           bool(body.end_of_stream))

    def _handle_buffered_chunk(
        self,
        state: _StreamState,
        raw: bytes,
        end_of_stream: bool,
    ) -> service_pb2.BodyResponse:
        """Accumulate non-streaming response chunks and transform on the last one."""
        state.body_buffer.extend(raw)
        logging.debug("Response body chunk: %d bytes, eos=%s, total=%d",
                      len(raw), end_of_stream, len(state.body_buffer))
        body_resp = service_pb2.BodyResponse()
        if not end_of_stream:
            # Suppress the chunk on the wire — we'll emit the full transformed
            # body once the upstream finishes. This is safe for non-streaming
            # responses where the client is waiting for a single JSON object.
            body_resp.response.body_mutation.body = b""
            return body_resp
        try:
            buf = bytes(state.body_buffer)
            if state.needs_response_transform:
                vertex_resp = json.loads(buf)
                openai_resp = transform_vertex_to_openai_response(
                    vertex_resp, model=state.model, provider=state.provider)
                out_bytes = json.dumps(openai_resp).encode("utf-8")
            else:
                # OpenAI-compat endpoint already returns OpenAI format.
                openai_resp = json.loads(buf)
                out_bytes = buf
            first_choice = (openai_resp.get("choices") or [{}])[0]
            output_text = (first_choice.get("message") or {}).get("content", "")
            logging.info("Output: %s", output_text[:200])
            body_resp.response.body_mutation.body = out_bytes
        except json.JSONDecodeError as e:
            logging.warning(
                "Invalid Vertex response body, passing through: %s", e)
            body_resp.response.body_mutation.body = bytes(state.body_buffer)
        except Exception:
            logging.exception(
                "Response transformation failed; passing through raw body")
            body_resp.response.body_mutation.body = bytes(state.body_buffer)
        return body_resp

    def _handle_streaming_chunk(
        self,
        state: _StreamState,
        raw: bytes,
        end_of_stream: bool,
    ) -> service_pb2.BodyResponse:
        """Transform Vertex SSE chunks to OpenAI SSE chunks on the fly.

        SSE events are delimited by `\\n\\n`. A single ext_proc body chunk may
        contain multiple complete events, a partial trailing event, or just a
        fragment of one event — accumulate in `state.sse_buffer` until we have
        complete events, emit the transformed events, and append `[DONE]` on
        end_of_stream.
        """
        # Vertex emits SSE with CRLF line endings; normalize so the splitter
        # below (which uses LF) handles either delimiter style.
        state.sse_buffer += raw.decode("utf-8", errors="replace").replace("\r\n", "\n")
        out = bytearray()
        while "\n\n" in state.sse_buffer:
            event, _, rest = state.sse_buffer.partition("\n\n")
            state.sse_buffer = rest
            data = _extract_sse_data(event)
            if data is None or data == "[DONE]":
                continue
            try:
                vertex_chunk = json.loads(data)
            except json.JSONDecodeError:
                logging.debug("Discarding non-JSON SSE event: %r", data[:200])
                continue
            try:
                openai_chunk, state.role_emitted = transform_vertex_sse_chunk_to_openai(
                    vertex_chunk,
                    chat_id=state.chat_id,
                    created=state.created_ts,
                    model=state.model,
                    role_emitted=state.role_emitted,
                )
            except Exception:
                logging.exception("SSE chunk transformation failed; skipping")
                continue
            out.extend(b"data: ")
            out.extend(json.dumps(openai_chunk).encode("utf-8"))
            out.extend(b"\n\n")
        if end_of_stream:
            out.extend(b"data: [DONE]\n\n")
        body_resp = service_pb2.BodyResponse()
        body_resp.response.body_mutation.body = bytes(out)
        return body_resp

    # ------------------------------------------------------------------ helpers

    def _detect_keywords(self, req_map: dict) -> list[str]:
        if not self.sec_keywords:
            return []
        messages = req_map.get("messages")
        if not isinstance(messages, list):
            return []
        seen: set[str] = set()
        matched: list[str] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content", "")
            if not isinstance(content, str):
                continue
            lower = content.lower()
            for kw in self.sec_keywords:
                if kw not in seen and kw in lower:
                    matched.append(kw)
                    seen.add(kw)
        return matched


def _extract_sse_data(event: str) -> str | None:
    """Extract the `data:` payload from a single SSE event block.

    SSE events can have multiple `data:` lines (concatenated) and may include
    `event:` / `id:` / `:comment` lines we ignore. Returns None if the event
    contains no data line.
    """
    parts: list[str] = []
    for line in event.split("\n"):
        if line.startswith("data:"):
            parts.append(line[len("data:"):].lstrip())
    if not parts:
        return None
    return "\n".join(parts)


def _resolve_provider(model: str) -> str:
    """Resolve the LiteLLM provider for a model name.

    Uses `litellm.get_llm_provider` when available, falling back to a
    slash-prefix heuristic if LiteLLM cannot identify the model.
    """
    if litellm is not None and model:
        try:
            _, provider, _, _ = litellm.get_llm_provider(model=model)
            if provider:
                return provider
        except Exception as e:
            logging.debug("get_llm_provider(%r) failed: %s", model, e)
    if "/" in model:
        return model.split("/", 1)[0].lower()
    return DEFAULT_PROVIDER


def _parse_csv_lower(csv: str) -> list[str]:
    if not csv:
        return []
    return [item.strip().lower() for item in csv.split(",") if item.strip()]


def _parse_csv_set(csv: str) -> set[str]:
    if not csv:
        return set()
    return {item.strip() for item in csv.split(",") if item.strip()}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    LiteLLMGatewayCallout(disable_tls=True).run()
