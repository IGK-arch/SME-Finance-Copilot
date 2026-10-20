"""Personal reviewer demos: one freshly seeded synthetic workspace per visitor.

Opt-in with SME_DEMO_SELF_SERVICE=1. Every demo is a complete, separate workspace
(own SQLite store, sandbox bank process, worker and business clock) in a folder under a
dedicated demos directory, so tenant isolation, the audit chain and idempotency are the
same as for the main workspace. The main workspace is never touched. Idle demos have
their processes stopped and are resumed on the next request; after the idle limit the
folder is deleted. Cleanup deletes only folders whose name is a demo id directly inside
the demos directory.
"""

from __future__ import annotations

import os
import secrets
import shutil
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from finance.asgi import Workspace
from finance.compute import shift
from finance.domain import FinanceError, Json, require
from finance.ingestion import snapshot
from finance.store import Store
from scripts.runtime import Runtime

DEMO_ID = re.compile(r"^[0-9a-f]{16}$")
SEEN = "last_seen"


def self_service_enabled() -> bool:
    return os.getenv("SME_DEMO_SELF_SERVICE") == "1"


def _positive(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = 0
    require(value > 0, "UNSAFE_CONFIGURATION", f"{name} must be a positive number")
    return value


@dataclass(frozen=True)
class DemoLimits:
    max_active: int = 12
    idle_hours: float = 6
    per_client: int = 3
    client_window_seconds: float = 3600
    stop_after_seconds: float = 1800

    @classmethod
    def environment(cls) -> DemoLimits:
        return cls(
            max_active=int(_positive("SME_DEMO_MAX_ACTIVE", 12)),
            idle_hours=_positive("SME_DEMO_IDLE_HOURS", 6),
            per_client=int(_positive("SME_DEMO_PER_IP_PER_HOUR", 3)),
        )


def controls(runtime: Runtime) -> tuple[Callable[[], Json], Callable[[Json], Json]]:
    """The demo clock and counterparty decisions of one workspace."""

    def advance() -> Json:
        company = runtime.store.company(runtime.ctx)
        # Settles submitted actions at the present tick before moving to the next event.
        with runtime.store.connect() as db:
            pending = db.execute(
                "SELECT 1 FROM actions WHERE status IN ('RESERVED','SUBMITTED','UNKNOWN') LIMIT 1"
            ).fetchone()
        if pending:
            return runtime.settle()
        # Use only observed contract/product dates, including approved extensions.
        # A fixed golden timeline would skip a newly negotiated due date.
        snap = snapshot(runtime.store, runtime.ctx)
        dates = [o["due_at"] for o in snap["obligations"] if o["outstanding_minor"]]
        dates += [p[key] for p in snap["financing_products"] for key in ("disburse_at", "repay_at")]
        next_at = min(
            (d for d in dates if d > company["clock"]), default=shift(company["clock"], 1)
        )
        runtime.admin("/admin/advance", {"clock": next_at})
        return runtime.service.refresh(runtime.ctx)

    return advance, lambda value: runtime.admin("/admin/extension", value)


def workspace(runtime: Runtime) -> Workspace:
    advance, decision = controls(runtime)
    return Workspace(runtime.service, advance, decision)


class DemoPool:
    def __init__(self, root: Path, limits: DemoLimits | None = None) -> None:
        root.mkdir(parents=True, exist_ok=True)
        self.root = root.resolve()
        self.limits = limits or DemoLimits()
        self.per_client = self.limits.per_client
        self.client_window_seconds = self.limits.client_window_seconds
        self.idle_hours = self.limits.idle_hours
        self.lock = threading.Lock()
        self.resume_lock = threading.Lock()
        self.active: dict[str, tuple[Runtime, Workspace]] = {}
        self.starting = 0
        self.stopped = threading.Event()
        self.sweeper: threading.Thread | None = None

    def folder(self, demo_id: str) -> Path | None:
        """Path of a demo folder, or None if the id is not a well-formed demo id."""
        if not DEMO_ID.match(demo_id):
            return None
        path = (self.root / demo_id).resolve()
        return path if path.parent == self.root else None

    def _touch(self, folder: Path) -> None:
        (folder / SEEN).write_text(str(time.time()), encoding="utf-8")

    def _last_seen(self, folder: Path) -> float:
        try:
            return float((folder / SEEN).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return folder.stat().st_mtime

    def _reserve_slot(self) -> None:
        with self.lock:
            if len(self.active) + self.starting >= self.limits.max_active:
                raise FinanceError(
                    "DEMO_CAPACITY", "All demo slots are busy, try again in a few minutes", True
                )
            self.starting += 1

    def _start(self, demo_id: str, folder: Path, resume: bool) -> Workspace:
        self._reserve_slot()
        runtime: Runtime | None = None
        try:
            runtime = Runtime(folder, resume=resume)
            runtime.start_worker()
            ws = workspace(runtime)
            self._touch(folder)
            with self.lock:
                self.active[demo_id] = (runtime, ws)
            return ws
        except BaseException:
            if runtime is not None:
                runtime.close()
            raise
        finally:
            with self.lock:
                self.starting -= 1

    def create(self) -> tuple[str, str, Workspace]:
        """A new seeded demo company; returns its id, OWNER token and workspace."""
        demo_id = secrets.token_hex(8)
        folder = self.folder(demo_id)
        assert folder is not None
        try:
            ws = self._start(demo_id, folder, resume=False)
        except BaseException:
            self._delete(demo_id)  # a half-seeded demo is never kept
            raise
        runtime = self.active[demo_id][0]
        return demo_id, runtime.tokens["OWNER"], ws

    def get(self, demo_id: str) -> Workspace | None:
        """The running demo, resumed if its processes were stopped; None if it is gone."""
        folder = self.folder(demo_id)
        if folder is None or not (folder / "runtime.secret.json").exists():
            return None
        # One resume at a time: two requests must never start processes for the same folder.
        with self.resume_lock:
            with self.lock:
                entry = self.active.get(demo_id)
            if entry is not None:
                self._touch(folder)
                return entry[1]
            return self._start(demo_id, folder, resume=True)

    def find(self, token: str) -> str | None:
        """Id of the demo whose membership token this is (to sign back in), or None."""
        for folder in sorted(self.root.iterdir()):
            database = folder / "observed" / "finance.db"
            if not DEMO_ID.match(folder.name) or not database.exists():
                continue
            try:
                Store(database).authenticate(token)
            except FinanceError:
                continue
            return folder.name
        return None

    def _stop(self, demo_id: str) -> None:
        with self.lock:
            entry = self.active.pop(demo_id, None)
        if entry is not None:
            entry[0].close()

    def _delete(self, demo_id: str) -> None:
        self._stop(demo_id)
        folder = self.folder(demo_id)
        if folder is not None and folder.is_dir():
            shutil.rmtree(folder, ignore_errors=True)

    def sweep(self, now: float | None = None) -> dict[str, list[str]]:
        """Stop idle demos' processes; delete demos idle longer than the limit."""
        moment = time.time() if now is None else now
        stopped, deleted = [], []
        for folder in list(self.root.iterdir()):
            if not folder.is_dir() or self.folder(folder.name) != folder.resolve():
                continue
            idle = moment - self._last_seen(folder)
            if idle > self.limits.idle_hours * 3600:
                self._delete(folder.name)
                deleted.append(folder.name)
            elif idle > self.limits.stop_after_seconds and folder.name in self.active:
                self._stop(folder.name)
                stopped.append(folder.name)
        return {"stopped": stopped, "deleted": deleted}

    def start_sweeper(self, interval: float = 300) -> None:
        def loop() -> None:
            while not self.stopped.wait(interval):
                try:
                    self.sweep()
                except Exception:  # keep sweeping; one bad folder must not stop cleanup
                    pass

        self.sweeper = threading.Thread(target=loop, name="demo-sweeper", daemon=True)
        self.sweeper.start()

    def close(self) -> None:
        self.stopped.set()
        for demo_id in list(self.active):
            self._stop(demo_id)
