from __future__ import annotations

import argparse
import os
from pathlib import Path

from finance.asgi import make_app
import uvicorn
from finance.domain import Config
from finance.gateway import ChatGateway, GatewayConfig
from scripts.demo_pool import DemoLimits, DemoPool, controls, self_service_enabled
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
    from finance.asgi import demo_login_role, public_origin

    origin = public_origin()
    demo_role = demo_login_role()
    directory = Path(args.directory)
    # Personal demos live next to the workspace, never inside it.
    pool = (
        DemoPool(directory.parent / (directory.name + "-demos"), DemoLimits.environment())
        if self_service_enabled()
        else None
    )
    with Runtime(directory, resume=True) as runtime:
        credentials_path = directory / "local-login.secret.json"
        advance, decision = controls(runtime)
        runtime.start_worker()
        app = make_app(
            runtime.service,
            advance,
            decision,
            (runtime.ctx, os.environ["SME_WEBHOOK_SECRET"])
            if os.getenv("SME_WEBHOOK_SECRET")
            else None,
            credentials_path,
            pool,
        )
        print(f"SME Finance Copilot: http://127.0.0.1:{args.port}", flush=True)
        if origin:
            print(f"Public origin (via reverse proxy): {origin}", flush=True)
        print(f"Local login tokens (keep private): {credentials_path.resolve()}", flush=True)
        if demo_role:
            print(f"Demo key: the sign-in page shows the {demo_role} token publicly", flush=True)
        if pool:
            limits = pool.limits
            print(
                f"Personal demos: up to {limits.max_active} at once in {pool.root}, "
                f"removed after {limits.idle_hours:g} h idle",
                flush=True,
            )
            pool.sweep()
            pool.start_sweeper()
        print(
            f"SYNTHETIC / SANDBOX / {GatewayConfig.environment().public()['mode']}. Press Ctrl+C to stop.",
            flush=True,
        )

        try:
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=args.port,
                access_log=False,
                proxy_headers=True,
                forwarded_allow_ips="127.0.0.1",
            )
        finally:
            if pool:
                pool.close()


if __name__ == "__main__":
    main()
