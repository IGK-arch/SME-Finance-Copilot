"""Strata chat-completions codec; financial tools still execute in our graph."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from finance.domain import FinanceError, Json, canonical, digest, require

if TYPE_CHECKING:
    from finance.gateway import GatewayConfig


def describe(config: GatewayConfig, request: Callable[..., Json]) -> Json:
    status = request("/v1/status")
    models = request("/v1/models")
    rows = models.get("data")
    require(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
        "INVALID_MODEL_OUTPUT",
        "Model list required",
    )
    assert isinstance(rows, list)
    require(
        status.get("service") == "strata"
        and status.get("loaded") is True
        and isinstance(status.get("engine"), str)
        and bool(status["engine"])
        and type(status.get("started")) is int,
        "MODEL_UNAVAILABLE",
        "A loaded Strata engine with instance metadata is required",
    )
    require(
        status.get("model") == config.model and config.model in {m.get("id") for m in rows},
        "MODEL_NOT_INSTALLED",
        "Configured model must exactly match the loaded Strata model",
    )
    context = status.get("cache_max_tokens")
    require(
        type(context) is int and context >= config.context_tokens,
        "CONTEXT_LIMIT",
        "Loaded Strata context is smaller than the requested context",
    )
    identity = {
        "model": config.model,
        "engine_version": status["engine"],
        "server_started": status["started"],
        "context_tokens": context,
    }
    return {
        **identity,
        "digest": digest(identity),
        "identity_scope": "STRATA_SERVICE_INSTANCE_METADATA_NOT_WEIGHT_HASH",
        "weight_digest": None,
        "license": None,
        "capabilities": ["chat_completions"],
    }


def wire_messages(messages: list[Json]) -> list[Json]:
    """Map durable graph tool names to protocol call IDs, never parse prose as calls."""
    result: list[Json] = []
    pending: list[tuple[str, str]] = []
    for index, message in enumerate(messages):
        role = message["role"]
        out = {"role": role, "content": message.get("content") or ""}
        if role == "assistant" and message.get("tool_calls"):
            require(not pending, "INVALID_MODEL_OUTPUT", "Unanswered tool calls in history")
            calls = []
            for position, call in enumerate(message["tool_calls"]):
                function = call["function"]
                call_id = call.get("id") or f"call_{index}_{position}"
                pending.append((call_id, function["name"]))
                calls.append(
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": function["name"],
                            "arguments": canonical(function["arguments"]),
                        },
                    }
                )
            out["tool_calls"] = calls
        if role == "tool":
            require(
                bool(pending) and pending[0][1] == message.get("tool_name"),
                "INVALID_MODEL_OUTPUT",
                "Tool result must match a preceding call",
            )
            out["tool_call_id"] = pending.pop(0)[0]
        result.append(out)
    require(not pending, "INVALID_MODEL_OUTPUT", "Tool call results are incomplete")
    return result


def completion(
    config: GatewayConfig,
    request: Callable[..., Json],
    messages: list[Json],
    tools: list[Json],
    timeout: float,
    attempt: Json,
) -> tuple[Json, Json]:
    body = {
        "model": config.model,
        "messages": wire_messages(messages),
        "tools": tools,
        "tool_choice": "auto" if tools else "none",
        "stream": False,
        "temperature": 0,
        "max_tokens": config.output_tokens,
        "reasoning_effort": "high" if config.think else "none",
    }
    attempt["request_hash"] = digest(body)
    output = request("/v1/chat/completions", body, timeout=timeout)
    require(output.get("model") == config.model, "MODEL_CHANGED", "Unexpected response model")
    choices = output.get("choices")
    require(
        isinstance(choices, list) and len(choices) == 1,
        "INVALID_MODEL_OUTPUT",
        "One completion required",
    )
    assert isinstance(choices, list)
    choice = choices[0]
    require(isinstance(choice, dict), "INVALID_MODEL_OUTPUT", "Completion must be an object")
    usage = output.get("usage")
    require(isinstance(usage, dict), "MODEL_USAGE_MISSING", "Provider token usage is required")
    assert isinstance(usage, dict)
    counts = [usage.get("prompt_tokens"), usage.get("completion_tokens"), usage.get("total_tokens")]
    require(
        all(type(n) is int and n >= 0 for n in counts)
        and counts[2] == sum(n for n in counts[:2] if isinstance(n, int)),
        "MODEL_USAGE_MISSING",
        "Valid consistent provider token counts are required",
    )
    measured = {
        "prompt_eval_count": counts[0],
        "eval_count": counts[1],
        "provider_usage": {
            k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
        },
        "done_reason": choice.get("finish_reason"),
        "measurement_source": "STRATA_RESPONSE_USAGE",
    }
    attempt.update(status="RECEIVED", metrics=measured)
    require(
        choice.get("finish_reason") != "length",
        "MODEL_OUTPUT_TRUNCATED",
        "Model exhausted its output limit",
    )
    require(
        choice.get("finish_reason") in {"stop", "tool_calls"},
        "INVALID_MODEL_OUTPUT",
        "Completed response required",
    )
    raw = choice.get("message")
    require(
        isinstance(raw, dict) and raw.get("role") == "assistant",
        "INVALID_MODEL_OUTPUT",
        "Assistant response required",
    )
    # Exclude reasoning_content and all other provider-only fields from durable state.
    content = raw.get("content") or ""
    require(isinstance(content, str), "INVALID_MODEL_OUTPUT", "Text response required")
    calls = raw.get("tool_calls") or []
    require(
        isinstance(calls, list) and len(calls) <= 4,
        "INVALID_MODEL_OUTPUT",
        "At most four tool calls",
    )
    normalized = []
    seen = set()
    for call in calls:
        require(isinstance(call, dict), "INVALID_MODEL_OUTPUT", "Tool call object required")
        function = call.get("function")
        call_id = call.get("id")
        require(
            call.get("type") == "function"
            and isinstance(function, dict)
            and isinstance(function.get("name"), str)
            and isinstance(call_id, str)
            and bool(call_id)
            and call_id not in seen,
            "INVALID_MODEL_OUTPUT",
            "Unique typed function call required",
        )
        seen.add(call_id)
        try:
            arguments = json.loads(function.get("arguments", ""))
        except (ValueError, TypeError) as exc:
            raise FinanceError("INVALID_MODEL_OUTPUT", "Tool arguments must be JSON") from exc
        require(
            isinstance(arguments, dict), "INVALID_MODEL_OUTPUT", "Tool arguments must be an object"
        )
        normalized.append(
            {
                "id": call_id,
                "type": "function",
                "function": {"name": function["name"], "arguments": arguments},
            }
        )
    require(
        bool(content.strip()) or bool(normalized),
        "INVALID_MODEL_OUTPUT",
        "Visible text or tool call required",
    )
    return {"role": "assistant", "content": content, "tool_calls": normalized}, measured
