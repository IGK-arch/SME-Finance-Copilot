"""Pure financial primitives. No model, network, database or simulator imports."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)
Json = dict[str, Any]


class FinanceError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable

    def envelope(self) -> Json:
        return {"code": self.code, "safe_message": self.safe_message, "retryable": self.retryable}


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FinanceError(code, message)


def minor(value: Any, *, positive: bool = False) -> int:
    require(type(value) is int, "INVALID_MONEY", "Money must be integer minor units")
    require(INT64_MIN <= value <= INT64_MAX, "MONEY_OVERFLOW", "Money exceeds int64")
    require(not positive or value > 0, "INVALID_MONEY", "Amount must be positive")
    return value


@dataclass(frozen=True)
class Money:
    amount_minor: int
    currency: str = "CNY"

    def __post_init__(self) -> None:
        minor(self.amount_minor)
        require(self.currency == "CNY", "UNSUPPORTED_CURRENCY", "Only CNY is supported")

    def __add__(self, other: Money) -> Money:
        require(self.currency == other.currency, "CURRENCY_MISMATCH", "Explicit FX required")
        return Money(minor(self.amount_minor + other.amount_minor), self.currency)


def rate_charge(amount: int, rate: str, days: int, basis: int = 365) -> int:
    minor(amount, positive=True)
    require(type(rate) is str and days >= 0 and basis > 0, "INVALID_RATE", "Invalid rate terms")
    try:
        decimal_rate = Decimal(rate)
        require(
            decimal_rate.is_finite() and decimal_rate >= 0, "INVALID_RATE", "Invalid rate terms"
        )
        result = Decimal(amount) * decimal_rate * Decimal(days) / Decimal(basis)
        return minor(int(result.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except (ValueError, ArithmeticError) as exc:
        raise FinanceError("INVALID_RATE", "Invalid decimal rate") from exc


def utc(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(dt.tzinfo is not None, "INVALID_TIME", "Timezone is required")
        return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, AttributeError) as exc:
        raise FinanceError("INVALID_TIME", "Invalid timestamp") from exc


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def available(provider_available: int, reservations: list[Json]) -> int:
    return minor(
        provider_available
        - sum(
            r["amount_minor"]
            for r in reservations
            if r["status"] == "ACTIVE" and not r["included_in_provider_available"]
        )
    )


@dataclass(frozen=True)
class AuthContext:
    tenant_id: str
    user_id: str
    role: str


@dataclass(frozen=True)
class Config:
    data_mode: str = "synthetic"
    execution_backend: str = "sandbox"
    model_provider: str = "mock"

    @classmethod
    def from_environment(cls) -> Config:
        for name in (
            "ALLOW_REAL_FINANCIAL_ACTIONS",
            "ALLOW_EXTERNAL_NOTIFICATIONS",
            "ALLOW_UNAPPROVED_DATA_EGRESS",
        ):
            require(
                os.getenv(name, "false").lower() == "false",
                "UNSAFE_CONFIGURATION",
                f"{name} must remain false",
            )
        result = cls(
            os.getenv("DATA_MODE", "synthetic"),
            os.getenv("EXECUTION_BACKEND", "sandbox"),
            os.getenv("MODEL_PROVIDER", "mock"),
        )
        require(
            result.data_mode == "synthetic" and result.execution_backend == "sandbox",
            "UNSUPPORTED_BACKEND",
            "Only synthetic sandbox execution is implemented",
        )
        require(
            result.model_provider in {"mock", "ollama", "strata", "disabled"},
            "UNSUPPORTED_MODEL_PROVIDER",
            "Supported modes: mock, disabled, explicitly enabled Ollama or Strata",
        )
        return result
