"""Read-only, secret-free runtime diagnostics and an explicitly gated live smoke."""

import argparse
import importlib.metadata
import json
import shutil
from pathlib import Path

from finance.domain import FinanceError, now
from finance.gateway import ChatGateway, GatewayConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    cfg = GatewayConfig.environment()
    result = {
        "at": now(),
        "model": cfg.public(),
        "postgresql_executable": bool(
            shutil.which("psql")
            or Path(".runtime/postgres/binaries/pgsql/bin/postgres.exe").exists()
        ),
        "docker_executable": bool(shutil.which("docker")),
        "dependencies": {
            p: importlib.metadata.version(p) for p in ("fastapi", "langgraph", "ortools", "pypdf")
        },
        "live_test": {"status": "NOT_RUN", "reason": "No live test requested"},
    }
    if args.live:
        if cfg.provider != "ollama" or not cfg.enabled or not cfg.model:
            result["live_test"] = {
                "status": "BLOCKED",
                "reason": "MODEL_PROVIDER=ollama, an installed MODEL_NAME and ALLOW_LOCAL_MODEL_INFERENCE=true are required. No inference performed.",
            }
        else:
            try:
                output = ChatGateway(cfg).chat(
                    [
                        {
                            "role": "user",
                            "content": "Respond with a brief greeting. This is a local synthetic smoke test.",
                        }
                    ],
                    [],
                    {},
                )
                result["live_test"] = {
                    "status": "PASSED",
                    "scope": "Provider connectivity only; not agent quality",
                    "output": output,
                }
            except FinanceError as exc:
                result["live_test"] = {"status": "FAILED", "error": exc.envelope()}
    path = Path("artifacts/live-smoke.json" if args.live else "artifacts/doctor.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
