"""Identity contract for our loopback llama.cpp benchmark sidecar, not a native status API."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

from finance.domain import Json, digest, require

if TYPE_CHECKING:
    from finance.gateway import GatewayConfig


def describe(config: GatewayConfig, request: Callable[..., Json]) -> Json:
    status, models = request("/v1/status"), request("/v1/models")
    require(
        status.get("service") == "llamacpp-bench"
        and status.get("loaded") is True
        and type(status.get("started")) is int
        and isinstance(status.get("engine"), str)
        and bool(status["engine"]),
        "MODEL_UNAVAILABLE",
        "A live llama.cpp benchmark sidecar with instance metadata is required",
    )
    rows = models.get("data")
    require(
        isinstance(rows, list)
        and all(isinstance(row, dict) for row in rows)
        and status.get("model") == config.model
        and any(row.get("id") == config.model for row in rows),
        "MODEL_CHANGED",
        "Loaded model must exactly match the configured alias",
    )
    context, weight = status.get("cache_max_tokens"), status.get("weight_sha256")
    require(
        type(context) is int and context >= config.context_tokens,
        "CONTEXT_LIMIT",
        "Loaded context is smaller than the requested context",
    )
    require(
        isinstance(weight, str) and re.fullmatch(r"[0-9a-f]{64}", weight) is not None,
        "MODEL_IDENTITY_MISSING",
        "Verified GGUF SHA-256 is required",
    )
    require(
        status.get("reasoning_mode") == "none" and not config.think,
        "INVALID_MODEL_CONFIG",
        "This fixed benchmark connection permits reasoning disabled only",
    )
    identity = {
        "model": config.model,
        "engine_version": status["engine"],
        "server_started": status["started"],
        "context_tokens": context,
        "weight_digest": weight,
    }
    return {
        **identity,
        "digest": digest(identity),
        "identity_scope": "LLAMACPP_INSTANCE_AND_VERIFIED_GGUF_SHA256",
        "capabilities": ["chat_completions"],
        "license": status.get("license"),
    }
