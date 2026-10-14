"""Windows process-tree commit limit and resource checks for local model runs.

The job limit bounds CPU committed memory, not GPU memory or other applications.
Disk checks are polling safeguards, not filesystem quotas. No system settings change.
"""

from __future__ import annotations

import ctypes as ct
from ctypes import wintypes as wt
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

GIB = 1024**3
RUNTIME_LIMIT_BYTES = 20 * GIB  # E: only; user requested an additional larger model.


class ResourceLimitError(RuntimeError):
    pass


class MemoryStatus(ct.Structure):
    _fields_ = [("length", wt.DWORD), ("load", wt.DWORD)] + [
        (name, ct.c_ulonglong)
        for name in (
            "total_phys",
            "available_phys",
            "total_commit",
            "available_commit",
            "total_virtual",
            "available_virtual",
            "available_extended",
        )
    ]


class BasicLimits(ct.Structure):
    _fields_ = [
        ("process_time", ct.c_longlong),
        ("job_time", ct.c_longlong),
        ("flags", wt.DWORD),
        ("min_working_set", ct.c_size_t),
        ("max_working_set", ct.c_size_t),
        ("active_process_limit", wt.DWORD),
        ("affinity", ct.c_size_t),
        ("priority", wt.DWORD),
        ("scheduling", wt.DWORD),
    ]


class ExtendedLimits(ct.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", ct.c_ulonglong * 6),
        ("process_memory", ct.c_size_t),
        ("job_memory", ct.c_size_t),
        ("peak_process", ct.c_size_t),
        ("peak_job", ct.c_size_t),
    ]


def kernel() -> Any:
    if os.name != "nt":
        raise ResourceLimitError("This resource-limited launcher requires Windows")
    return ct.WinDLL("kernel32", use_last_error=True)


def tree_bytes(root: Path) -> int:
    size = 0
    for directory, folders, files in os.walk(root):
        for name in folders + files:
            path = Path(directory) / name
            try:
                info = path.lstat()
            except FileNotFoundError:
                continue  # Ollama atomically renames completed partial downloads.
            if getattr(info, "st_file_attributes", 0) & 0x400 or path.is_symlink():
                raise ResourceLimitError(f"Reparse point refused in model storage: {path}")
        for name in files:
            try:
                size += (Path(directory) / name).stat().st_size
            except FileNotFoundError:
                continue
    return size


def resource_snapshot(root: Path) -> dict[str, int]:
    memory = MemoryStatus()
    memory.length = ct.sizeof(memory)
    if not kernel().GlobalMemoryStatusEx(ct.byref(memory)):
        raise ct.WinError(ct.get_last_error())
    return {
        "system_free_bytes": shutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\").free,
        "workspace_free_bytes": shutil.disk_usage(root.anchor).free,
        "available_ram_bytes": memory.available_phys,
        "available_commit_bytes": memory.available_commit,
        "runtime_bytes": tree_bytes(root),
    }


def check_resources(
    sample: dict[str, int], *, starting: bool = False, extra_bytes: int = 0
) -> None:
    floors = {
        "system_free_bytes": (6 if starting else 4) * GIB,
        "workspace_free_bytes": 20 * GIB + extra_bytes,
        "available_ram_bytes": (10 if starting else 5) * GIB,
        "available_commit_bytes": (8 if starting else 3) * GIB,
    }
    for key, floor in floors.items():
        if sample[key] < floor:
            raise ResourceLimitError(f"{key} below reserve: {sample[key]} < {floor}")
    if sample["runtime_bytes"] + extra_bytes > RUNTIME_LIMIT_BYTES:
        raise ResourceLimitError("Project model runtime would exceed 20 GiB on E:")


class Singleton:
    """Kernel handle, automatically released if the launcher exits/crashes."""

    def __init__(self, name: str) -> None:
        self.api = kernel()
        self.api.CreateMutexW.argtypes = [ct.c_void_p, wt.BOOL, wt.LPCWSTR]
        self.api.CreateMutexW.restype = wt.HANDLE
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.handle = self.api.CreateMutexW(None, False, name)
        error = ct.get_last_error()
        if not self.handle:
            raise ct.WinError(error)
        if error == 183:  # ERROR_ALREADY_EXISTS
            self.close()
            raise ResourceLimitError("Another guarded local-model operation is already running")

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> Singleton:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class WindowsJob:
    """Fail closed: child waits on stdin until it has joined the bounded job."""

    def __init__(self, memory_bytes: int = 2 * GIB) -> None:
        self.api = kernel()
        self.api.CreateJobObjectW.argtypes = [ct.c_void_p, wt.LPCWSTR]
        self.api.CreateJobObjectW.restype = wt.HANDLE
        self.api.SetInformationJobObject.argtypes = [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD]
        self.api.QueryInformationJobObject.argtypes = [
            wt.HANDLE,
            ct.c_int,
            ct.c_void_p,
            wt.DWORD,
            ct.c_void_p,
        ]
        self.api.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        self.api.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.api.OpenProcess.restype = wt.HANDLE
        self.api.CloseHandle.argtypes = [wt.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ct.WinError(ct.get_last_error())
        limits = ExtendedLimits()
        # JOB_MEMORY | KILL_ON_JOB_CLOSE | ACTIVE_PROCESS; breakaway is not allowed.
        limits.basic.flags = 0x200 | 0x2000 | 0x8
        limits.basic.active_process_limit = 8
        limits.job_memory = memory_bytes
        if not self.api.SetInformationJobObject(
            self.handle, 9, ct.byref(limits), ct.sizeof(limits)
        ):
            error = ct.get_last_error()
            self.close()
            raise ct.WinError(error)

    def start(self, command: list[str], **kwargs: Any) -> subprocess.Popen:
        process = subprocess.Popen(
            [sys.executable, "-m", "scripts.resource_guard", "--child", *command],
            stdin=subprocess.PIPE,
            **kwargs,
        )
        handle = self.api.OpenProcess(0x100 | 0x1, False, process.pid)  # SET_QUOTA | TERMINATE
        try:
            if not handle or not self.api.AssignProcessToJobObject(self.handle, handle):
                raise ct.WinError(ct.get_last_error())
            assert process.stdin is not None
            process.stdin.write(b"G")
            process.stdin.flush()
            process.stdin.close()
            process.stdin = None
        except BaseException:
            process.kill()
            process.wait(timeout=10)
            raise
        finally:
            if handle:
                self.api.CloseHandle(handle)
        return process

    def peak_bytes(self) -> int:
        limits = ExtendedLimits()
        if not self.api.QueryInformationJobObject(
            self.handle, 9, ct.byref(limits), ct.sizeof(limits), None
        ):
            raise ct.WinError(ct.get_last_error())
        return limits.peak_job

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> WindowsJob:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


if __name__ == "__main__":
    if sys.argv[1:2] != ["--child"] or sys.stdin.buffer.read(1) != b"G":
        raise SystemExit("Refusing to launch an unarmed child")
    raise SystemExit(subprocess.call(sys.argv[2:], stdin=subprocess.DEVNULL))
