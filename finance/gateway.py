"""Explicit Ollama/Strata chat contracts; no mock fallback on live errors."""

from __future__ import annotations

import json
import hashlib
import os
import time
from http.client import HTTPException
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from finance.adapter import NoRedirect
from finance.domain import FinanceError, Json, canonical, require

# Granite's official Ollama template adds this protocol only when no custom
# system message exists. Preserve the application's system rules and restore
# the model-specific wire format; never parse prose/code fences as tool calls.
GRANITE_TOOL_PROTOCOL = """When a provided tool is required, respond only with <|tool_call|> followed by a JSON list of calls with name and arguments fields, for example [{"name":"tool_name","arguments":{}}]. Use only the available tool names and their exact argument schemas. Do not put tool calls in Markdown code fences or describe them as future work. If no tool is needed, answer normally in the user's language. This format does not grant permission to approve or execute actions."""


def visible_message(message: Json) -> Json:
    """Normalize providers which leak tagged reasoning into content, without retaining it."""
    result = {k: v for k, v in message.items() if k in {"role", "content", "tool_calls"}}
    content = result.get("content", "")
    if isinstance(content, str):
        if "</think>" in content:
            content = content.rsplit("</think>", 1)[1].strip()
        if "<think>" in content:
            content = content.split("<think>", 1)[0].strip()
        result["content"] = content
    return result


@dataclass(frozen=True)
class GatewayConfig:
    provider: str = "mock"
    model: str = ""
    base_url: str = "http://127.0.0.1:11434"
    enabled: bool = False
    secret_env: str = "SME_MODEL_SECRET"
    max_steps: int = 12
    max_tokens: int = 64000
    timeout_seconds: int = 20
    max_elapsed_seconds: int = 120
    max_billed_cost_minor: int = 0
    context_tokens: int = 8192
    output_tokens: int = 1024
    think: bool = False
    strata_reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        require(
            self.strata_reasoning_effort in {None, "none", "low", "medium", "high"}
            and (self.strata_reasoning_effort is None or self.provider == "strata"),
            "INVALID_MODEL_CONFIG",
            "Explicit Strata reasoning effort must be none, low, medium or high",
        )
        require(
            1 <= self.timeout_seconds <= 240
            and 1 <= self.max_elapsed_seconds <= 600
            and 2048 <= self.context_tokens <= 32768
            and 128 <= self.output_tokens <= 4096,
            "INVALID_MODEL_CONFIG",
            "Model time/context/output limits are outside permitted bounds",
        )

    @classmethod
    def environment(cls) -> GatewayConfig:
        provider = os.getenv("MODEL_PROVIDER", "mock")
        return cls(
            provider=provider,
            model=os.getenv("MODEL_NAME", ""),
            base_url=os.getenv("MODEL_BASE_URL", "http://127.0.0.1:11434"),
            enabled=os.getenv(
                "ALLOW_SERVER_MODEL_INFERENCE"
                if provider in {"strata", "llamacpp"}
                else "ALLOW_LOCAL_MODEL_INFERENCE",
                "false",
            )
            == "true",
            timeout_seconds=int(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
            max_elapsed_seconds=int(os.getenv("MODEL_MAX_ELAPSED_SECONDS", "240")),
            context_tokens=int(os.getenv("MODEL_CONTEXT_TOKENS", "8192")),
            output_tokens=int(os.getenv("MODEL_OUTPUT_TOKENS", "1024")),
        )

    def public(self) -> Json:
        return {
            "provider": self.provider,
            "model": self.model or None,
            "mode": "MOCK"
            if self.provider == "mock"
            else "LIVE"
            if self.provider in {"ollama", "strata", "llamacpp"} and self.enabled and self.model
            else "DISABLED",
            "configured": self.provider == "mock" or bool(self.enabled and self.model),
            "max_steps": self.max_steps,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_elapsed_seconds": self.max_elapsed_seconds,
            "max_billed_cost_minor": self.max_billed_cost_minor,
            "context_tokens": self.context_tokens,
            "output_tokens": self.output_tokens,
            "think": self.think,
            "strata_reasoning_effort": self.strata_reasoning_effort,
            "execution_device": "self_hosted_server"
            if self.provider in {"strata", "llamacpp"}
            else "cpu",
            "batch_tokens": None if self.provider in {"strata", "llamacpp"} else 128,
            "memory_mapped_weights": None if self.provider in {"strata", "llamacpp"} else True,
        }


class ChatGateway:
    def __init__(
        self, config: GatewayConfig | None = None, scripted: list[Json] | None = None
    ) -> None:
        self.config = config or GatewayConfig.environment()
        self.scripted = scripted
        self.local_model: Json | None = None
        self.last_attempt: Json = {}

    def describe(self) -> Json:
        """Check provider identity (weight digest or Strata instance); never pull weights."""
        if self.config.provider == "llamacpp":
            from finance.llamacpp import describe

            return describe(self.config, self._request)
        if self.config.provider == "strata":
            from finance.strata import describe

            return describe(self.config, self._request)
        installed = self._request("/api/tags")
        entry = next(
            (m for m in installed.get("models", []) if m.get("name") == self.config.model),
            None,
        )
        require(
            entry is not None, "MODEL_NOT_INSTALLED", "Model must exactly match an installed name"
        )
        assert entry is not None
        details = self._request("/api/show", {"model": self.config.model})
        require(
            not details.get("remote_model")
            and not details.get("remote_host")
            and not entry.get("remote_model")
            and not entry.get("remote_host")
            and bool(details.get("details", {}).get("parameter_size")),
            "MODEL_EGRESS_DENIED",
            "Only installed local weights are permitted; cloud aliases are refused",
        )
        require(
            "tools" in details.get("capabilities", []),
            "MODEL_TOOLS_UNSUPPORTED",
            "Model must support tools",
        )
        return {
            "model": self.config.model,
            "digest": entry.get("digest"),
            "size_bytes": entry.get("size"),
            "details": details.get("details"),
            "capabilities": details.get("capabilities"),
            "license": details.get("license"),
        }

    def _request(self, path: str, value: Json | None = None, timeout: float | None = None) -> Json:
        config = self.config
        parsed = urlparse(config.base_url)
        require(
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.path in ("", "/")
            and not parsed.username
            and not parsed.query
            and not parsed.fragment,
            "MODEL_EGRESS_DENIED",
            "Only a configured loopback model endpoint is authorized",
        )
        require(
            config.enabled and bool(config.model),
            "MODEL_DISABLED",
            "Set a locally installed model and explicitly enable local inference",
        )
        headers = {"Content-Type": "application/json"}
        require(
            config.provider not in {"strata", "llamacpp"} or bool(os.getenv(config.secret_env)),
            "MODEL_DISABLED",
            "Server inference requires the authenticated SSH bridge token",
        )
        if secret := os.getenv(config.secret_env):
            headers["Authorization"] = "Bearer " + secret
        request = Request(
            config.base_url.rstrip("/") + path,
            data=canonical(value).encode() if value is not None else None,
            headers=headers,
        )
        try:
            with build_opener(ProxyHandler({}), NoRedirect).open(
                request, timeout=timeout or config.timeout_seconds
            ) as response:
                raw = response.read(1000001)
                require(
                    len(raw) <= 1000000, "MODEL_RESPONSE_LIMIT", "Model response limit exceeded"
                )
                result = json.loads(raw)
                require(isinstance(result, dict), "INVALID_MODEL_OUTPUT", "JSON object required")
                return result
        except (OSError, HTTPException, ValueError) as exc:
            raise FinanceError(
                "MODEL_UNAVAILABLE", "Local model request failed; no fallback used", True
            ) from exc

    def chat(self, messages: list[Json], tools: list[Json], usage: Json) -> Json:
        # A preflight rejection must not reuse the previous request's measurements.
        self.last_attempt = {"status": "NOT_SENT"}
        cfg = self.config
        require(
            cfg.max_billed_cost_minor == 0
            and cfg.provider in {"mock", "ollama", "strata", "llamacpp", "disabled"},
            "MODEL_COST_POLICY_DENIED",
            "Only offline fixtures or a local endpoint with no billed API are permitted",
        )
        remaining_time = cfg.max_elapsed_seconds - usage.get("elapsed_seconds", 0)
        require(remaining_time > 0, "BUDGET_EXCEEDED", "Model wall-time budget exhausted")
        require(
            usage.get("calls", 0) < cfg.max_steps, "BUDGET_EXCEEDED", "Model step budget exhausted"
        )
        require(
            len(canonical(messages)) <= 50000, "CONTEXT_LIMIT", "Context exceeds permitted size"
        )
        # Character count is a conservative pre-call bound, not a reported token metric.
        require(
            usage.get("tokens", 0) + len(canonical(messages)) + cfg.output_tokens <= cfg.max_tokens,
            "BUDGET_EXCEEDED",
            "Remaining token budget cannot cover this request",
        )
        start = time.monotonic()
        self.last_attempt = {"status": "STARTED"}
        measured: Json = {}
        if cfg.provider == "mock":
            index = usage.get("calls", 0)
            if self.scripted is not None:
                message = self.scripted[min(index, len(self.scripted) - 1)]
            else:
                # Explicit fixture sequence. It is not natural language understanding.
                results = [m for m in messages if m["role"] == "tool"]
                snap = next(
                    (
                        json.loads(m["content"])["result"]["snapshot_id"]
                        for m in results
                        if m.get("tool_name") == "get_financial_snapshot"
                    ),
                    None,
                )
                sequence = [
                    ("get_financial_snapshot", {}),
                    ("calculate_business_metrics", {"snapshot_id": snap}),
                    ("forecast_cashflow", {"snapshot_id": snap}),
                    ("screen_financing_products", {"snapshot_id": snap}),
                    ("optimize_plan", {"objective": "MIN_COST"}),
                ]
                message = (
                    {"role": "assistant", "content": "Offline fixture completed."}
                    if index >= len(sequence)
                    else {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": sequence[index][0],
                                    "arguments": sequence[index][1],
                                }
                            }
                        ],
                    }
                )
            tokens = 0
        elif cfg.provider in {"strata", "llamacpp"}:
            from finance.strata import completion

            identity = self.describe()
            require(
                self.local_model is None or identity["digest"] == self.local_model["digest"],
                "MODEL_CHANGED",
                "Model service instance changed; start a new workflow",
            )
            self.local_model = identity
            remaining_time -= time.monotonic() - start
            require(remaining_time > 0, "BUDGET_EXCEEDED", "Model wall-time budget exhausted")
            message, measured = completion(
                cfg,
                self._request,
                messages,
                tools,
                min(cfg.timeout_seconds, remaining_time),
                self.last_attempt,
            )
            message = visible_message(message)
            tokens = measured["prompt_eval_count"] + measured["eval_count"]
        else:
            require(
                cfg.provider == "ollama",
                "UNSUPPORTED_MODEL_PROVIDER",
                "Only mock or local Ollama is supported",
            )
            if self.local_model is None:
                self.local_model = self.describe()
            installed = self._request("/api/tags", timeout=min(cfg.timeout_seconds, remaining_time))
            require(
                cfg.model in {m.get("name") for m in installed.get("models", [])},
                "MODEL_NOT_INSTALLED",
                "Configured model must exactly match a locally installed model name",
            )
            remaining_time -= time.monotonic() - start
            require(remaining_time > 0, "BUDGET_EXCEEDED", "Model wall-time budget exhausted")
            request_messages = messages
            if tools and (self.local_model or {}).get("details", {}).get("family") == "granite":
                request_messages = [
                    dict(m, content=m.get("content", "") + "\n\n" + GRANITE_TOOL_PROTOCOL)
                    if m.get("role") == "system"
                    else m
                    for m in messages
                ]
                if not any(m.get("role") == "system" for m in messages):
                    request_messages = [
                        {"role": "system", "content": GRANITE_TOOL_PROTOCOL}
                    ] + messages
            if (
                not cfg.think
                and (self.local_model or {}).get("details", {}).get("family") == "qwen3"
            ):
                # Official Qwen3 soft switch, in addition to Ollama's native switch.
                request_messages = [
                    dict(m, content=m.get("content", "") + "\n/no_think")
                    if m.get("role") == "system"
                    else m
                    for m in messages
                ]
                if not any(m.get("role") == "system" for m in messages):
                    request_messages = [{"role": "system", "content": "/no_think"}] + messages
            request_body = {
                "model": cfg.model,
                "messages": request_messages,
                "tools": tools,
                "stream": False,
                "think": cfg.think,
                "keep_alive": "60s",
                "options": {
                    "temperature": 0,
                    "seed": 0,
                    "num_predict": cfg.output_tokens,
                    "num_ctx": cfg.context_tokens,
                    "num_gpu": 0,
                    "num_batch": 128,
                    "use_mmap": True,
                },
            }
            self.last_attempt["request_hash"] = hashlib.sha256(
                canonical(request_body).encode()
            ).hexdigest()
            output = self._request(
                "/api/chat",
                request_body,
                timeout=min(cfg.timeout_seconds, remaining_time),
            )
            message = output.get("message")
            require(
                isinstance(message, dict) and output.get("done") is True,
                "INVALID_MODEL_OUTPUT",
                "Completed chat response required",
            )
            message = visible_message(message)
            counts = [output.get("prompt_eval_count"), output.get("eval_count")]
            require(
                all(type(v) is int and v >= 0 for v in counts),
                "MODEL_USAGE_MISSING",
                "Provider token usage is required",
            )
            tokens = sum(int(v) for v in counts if v is not None)
            measured = {
                key: output.get(key)
                for key in (
                    "prompt_eval_count",
                    "eval_count",
                    "total_duration",
                    "load_duration",
                    "prompt_eval_duration",
                    "eval_duration",
                    "done_reason",
                )
            }
            self.last_attempt.update(status="RECEIVED", metrics=measured)
            require(
                output.get("done_reason") != "length",
                "MODEL_OUTPUT_TRUNCATED",
                "Model exhausted its output limit; incomplete output is not success",
            )
            require(
                message.get("role") == "assistant"
                and isinstance(message.get("content", ""), str)
                and (bool(message.get("content", "").strip()) or bool(message.get("tool_calls"))),
                "INVALID_MODEL_OUTPUT",
                "A visible answer or tool call is required",
            )
            calls = message.get("tool_calls", [])
            require(
                isinstance(calls, list)
                and len(calls) <= 4
                and all(
                    isinstance(call, dict)
                    and isinstance(call.get("function"), dict)
                    and isinstance(call["function"].get("name"), str)
                    and isinstance(call["function"].get("arguments"), dict)
                    for call in calls
                ),
                "INVALID_MODEL_OUTPUT",
                "Tool calls must contain typed function names and argument objects",
            )
        require(
            usage.get("elapsed_seconds", 0) + time.monotonic() - start <= cfg.max_elapsed_seconds,
            "BUDGET_EXCEEDED",
            "Model wall-time budget exhausted",
        )
        require(
            usage.get("tokens", 0) + tokens <= cfg.max_tokens,
            "BUDGET_EXCEEDED",
            "Token budget exceeded",
        )
        self.last_attempt.update(status="ACCEPTED", metrics=measured)
        return {
            "message": message,
            "usage": {
                "calls": usage.get("calls", 0) + 1,
                "tokens": usage.get("tokens", 0) + tokens,
                "elapsed_seconds": usage.get("elapsed_seconds", 0) + time.monotonic() - start,
                "cost": None,
                "billing": "SELF_HOSTED_SERVER_NO_BILLED_MODEL_API"
                if cfg.provider in {"strata", "llamacpp"}
                else "LOCAL_ENDPOINT_NO_BILLED_API",
                "live_metrics_status": "NOT_RUN"
                if cfg.provider == "mock"
                else "MEASURED_PROVIDER_USAGE",
                "last_request": measured,
                "prompt_tokens": usage.get("prompt_tokens", 0)
                + measured.get("prompt_eval_count", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
                + measured.get("eval_count", 0),
            },
        }
