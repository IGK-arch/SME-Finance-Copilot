from __future__ import annotations

import argparse
import os
from pathlib import Path

from finance.asgi import make_app
import uvicorn
from finance.domain import Config
from finance.gateway import ChatGateway, GatewayConfig
from finance.compute import shift
from finance.ingestion import snapshot
from scripts.runtime import Runtime
from scripts.local_llm import ROOT, require_guard


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--directory", default=".runtime/workspace")
    parser.add_argument(
        "--model", help="Exact installed local Ollama model; opts into local inference"
    )
    args = parser.parse_args()
    if args.model:
        os.environ.update(
            MODEL_PROVIDER="ollama", MODEL_NAME=args.model, ALLOW_LOCAL_MODEL_INFERENCE="true"
        )
    if GatewayConfig.environment().provider == "ollama":
        require_guard(ROOT)
        info = ChatGateway().describe()
        print(f"Local weights verified: {info['model']} / {info['digest']}", flush=True)
    elif GatewayConfig.environment().provider == "strata":
        info = ChatGateway().describe()
        print(
            f"Strata instance verified: {info['model']} / engine {info['engine_version']}",
            flush=True,
        )
    Config.from_environment()
    directory = Path(args.directory)
    with Runtime(directory, resume=True) as runtime:
        credentials_path = directory / "local-login.secret.json"

        def advance() -> dict:
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
            dates += [
                p[key] for p in snap["financing_products"] for key in ("disburse_at", "repay_at")
            ]
            next_at = min(
                (d for d in dates if d > company["clock"]), default=shift(company["clock"], 1)
            )
            runtime.admin("/admin/advance", {"clock": next_at})
            return runtime.service.refresh(runtime.ctx)

        runtime.start_worker()
        app = make_app(
            runtime.service,
            advance,
            lambda value: runtime.admin("/admin/extension", value),
            (runtime.ctx, os.environ["SME_WEBHOOK_SECRET"])
            if os.getenv("SME_WEBHOOK_SECRET")
            else None,
        )
        print(f"SME Finance Copilot: http://127.0.0.1:{args.port}", flush=True)
        print(f"Local login tokens (keep private): {credentials_path.resolve()}", flush=True)
        print(
            f"SYNTHETIC / SANDBOX / {GatewayConfig.environment().public()['mode']}. Press Ctrl+C to stop.",
            flush=True,
        )
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
