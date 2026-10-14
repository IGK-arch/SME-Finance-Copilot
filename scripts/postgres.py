"""Explicit local PostgreSQL lifecycle; no service installation or data deletion."""

from __future__ import annotations

import argparse
import json
import secrets
import socket
import subprocess
from pathlib import Path

from psycopg.conninfo import make_conninfo

from finance.domain import require
from finance.postgres import migrate, provision
from scripts.runtime import ORIGIN, PROFILE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["init", "start", "stop", "status", "provision", "migrate"]
    )
    parser.add_argument("--root", default=".runtime/postgres")
    parser.add_argument("--workspace", default=".runtime/pg-workspace")
    parser.add_argument("--tenant", default="demo_company")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    binary = root / "binaries/pgsql/bin"
    config_file = root / "cluster.secret.json"
    data = root / "data"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if args.action == "init":
        require(
            not config_file.exists() and not data.exists(),
            "CLUSTER_EXISTS",
            "Existing cluster is preserved",
        )
        require(
            (binary / "initdb.exe").exists(),
            "POSTGRES_MISSING",
            "Read docs/runbooks/postgres.md for the official archive",
        )
        password = secrets.token_urlsafe(40)
        password_file = root / "bootstrap-password.secret.txt"
        password_file.write_text(password, encoding="utf-8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        try:
            subprocess.run(
                [
                    str(binary / "initdb.exe"),
                    "-D",
                    str(data),
                    "-U",
                    "postgres",
                    "--auth=scram-sha-256",
                    "--encoding=UTF8",
                    "--locale=C",
                    "--pwfile=" + str(password_file),
                ],
                check=True,
                creationflags=flags,
            )
        finally:
            password_file.unlink(missing_ok=True)
        config_file.write_text(
            json.dumps(
                {
                    "port": port,
                    "dsn": make_conninfo(
                        host="127.0.0.1",
                        port=port,
                        dbname="postgres",
                        user="postgres",
                        password=password,
                        connect_timeout=5,
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print("Cluster initialized; SCRAM authentication. Start it explicitly.")
        return
    require(config_file.exists(), "POSTGRES_MISSING", "Initialize the local cluster first")
    config = json.loads(config_file.read_text(encoding="utf-8"))
    if args.action == "migrate":
        migrate(config["dsn"])
        print("PostgreSQL forward migrations applied; existing records preserved.")
        return
    if args.action == "provision":
        directory = Path(args.workspace)
        require(
            not (directory / "runtime.secret.json").exists()
            and not (directory / "postgres.secret.json").exists(),
            "WORKSPACE_EXISTS",
            "Provision into a fresh workspace; existing state is preserved",
        )
        migrate(config["dsn"])
        store, tokens = provision(
            config["dsn"], args.tenant, PROFILE, ORIGIN, directory / "observed"
        )
        (directory / "postgres.secret.json").write_text(
            json.dumps({"dsn": store.dsn, "tenant": args.tenant, "tokens": tokens}),
            encoding="utf-8",
        )
        print(
            f"PostgreSQL workspace provisioned: {directory.resolve()}. Admin credentials are not used by API/worker."
        )
        return
    command = [str(binary / "pg_ctl.exe"), args.action, "-D", str(data)]
    if args.action == "start":
        command += ["-l", str(root / "server.log"), "-o", f"-h 127.0.0.1 -p {config['port']}", "-w"]
    elif args.action == "stop":
        command += ["-m", "fast", "-w"]
    completed = subprocess.run(command, creationflags=flags)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
