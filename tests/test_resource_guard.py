"""Resource incident regressions, including actual Windows kernel enforcement."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
import json

from scripts.resource_guard import GIB, ResourceLimitError, Singleton, WindowsJob, check_resources
from scripts.local_llm import local_environment, write_status


class ResourceGuardTests(unittest.TestCase):
    def test_cache_profile_is_bounded_and_keeps_local_cpu_context_controls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for cache in ("q8_0", "q4_0"):
                with patch.dict(os.environ, {"SME_OLLAMA_KV_CACHE_TYPE": cache}):
                    env = local_environment(Path(directory))
                self.assertEqual(env["OLLAMA_KV_CACHE_TYPE"], cache)
                self.assertEqual(env["LLAMA_ARG_CACHE_RAM"], "0")
                self.assertEqual(env["OLLAMA_CONTEXT_LENGTH"], "8192")
                self.assertEqual(env["OLLAMA_NUM_PARALLEL"], "1")
                self.assertEqual(env["OLLAMA_NO_CLOUD"], "1")
                self.assertEqual(env["CUDA_VISIBLE_DEVICES"], "-1")
                self.assertEqual(env["OLLAMA_HOST"], "127.0.0.1:11434")
            with patch.dict(os.environ, {"SME_OLLAMA_KV_CACHE_TYPE": "unbounded"}):
                with self.assertRaises(ResourceLimitError):
                    local_environment(Path(directory))

    def test_status_write_retries_transient_windows_sharing_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replace = Path.replace
            calls = []

            def locked_once(path, target):
                calls.append(target)
                if len(calls) == 1:
                    raise PermissionError("reader holds file")
                return replace(path, target)

            with patch.object(Path, "replace", locked_once):
                write_status(root, {"status": "RUNNING"})
            self.assertEqual(
                json.loads((root / "guard-status.json").read_text())["status"], "RUNNING"
            )
            with patch.object(Path, "replace", side_effect=PermissionError("permanent")):
                with patch("scripts.local_llm.time.sleep"), self.assertRaises(PermissionError):
                    write_status(root, {"status": "FAILED"})

    def test_low_disk_ram_commit_or_footprint_refuses(self) -> None:
        good = dict(
            system_free_bytes=16 * GIB,
            workspace_free_bytes=40 * GIB,
            available_ram_bytes=13 * GIB,
            available_commit_bytes=16 * GIB,
            runtime_bytes=2 * GIB,
        )
        check_resources(good, starting=True)
        for key, value in {
            "system_free_bytes": 3 * GIB,
            "workspace_free_bytes": 19 * GIB,
            "available_ram_bytes": 4 * GIB,
            "available_commit_bytes": 2 * GIB,
            "runtime_bytes": 21 * GIB,
        }.items():
            with self.subTest(key=key), self.assertRaises(ResourceLimitError):
                check_resources({**good, key: value})
        with self.assertRaises(ResourceLimitError):
            check_resources({**good, "runtime_bytes": 14 * GIB}, extra_bytes=7 * GIB)
        # Third model storage is allowed on E:, while every system reserve stays.
        check_resources({**good, "runtime_bytes": 11 * GIB}, extra_bytes=7 * GIB)

    @unittest.skipUnless(os.name == "nt", "Windows kernel integration")
    def test_singleton_rejects_duplicate_and_recovers_after_close(self) -> None:
        name = "Local\\SMEGuardTest" + uuid.uuid4().hex
        with Singleton(name):
            with self.assertRaises(ResourceLimitError):
                Singleton(name)
        with Singleton(name):
            pass

    @unittest.skipUnless(os.name == "nt", "Windows kernel integration")
    def test_job_rejects_large_allocation_in_descendant(self) -> None:
        with WindowsJob(128 * 1024**2) as job:
            process = job.start(
                [sys.executable, "-c", "x=bytearray(256*1024**2)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, error = process.communicate(timeout=20)
            self.assertNotEqual(process.returncode, 0)
            self.assertIn(b"MemoryError", error)
            # Windows' peak counter can include a denied allocation; MemoryError
            # and nonzero exit prove rejection. Verify a smaller allocation works.
            smaller = job.start(
                [sys.executable, "-c", "x=bytearray(32*1024**2)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, error = smaller.communicate(timeout=20)
            self.assertEqual(smaller.returncode, 0, error)

    @unittest.skipUnless(os.name == "nt", "Windows kernel integration")
    def test_job_close_kills_process_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "started"
            job = WindowsJob(128 * 1024**2)
            process = job.start(
                [
                    sys.executable,
                    "-c",
                    "import pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text('ready'); time.sleep(30)",
                    str(marker),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(marker.exists())
            finally:
                job.close()
            self.assertIsNotNone(process.wait(timeout=5))


if __name__ == "__main__":
    unittest.main()
