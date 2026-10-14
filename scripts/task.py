"""Cross-platform task interface; does not delete data or kill unrelated processes."""

from __future__ import annotations

import argparse
import json
import platform
import importlib.metadata
from pathlib import Path

from finance.domain import Config
from finance.store import Store
from scripts.runtime import csv_bytes, golden_rows
from scripts.runtime import Runtime


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("task", choices=["setup", "migrate", "seed-demo", "down"])
    parser.add_argument("--directory", default=".runtime/workspace")
    args = parser.parse_args()
    Config.from_environment()
    if args.task == "setup":
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "runtime_dependencies": {
                        p: importlib.metadata.version(p)
                        for p in ("fastapi", "langgraph", "ortools", "pypdf", "psycopg")
                    },
                    "mode": "synthetic/sandbox/mock",
                }
            )
        )
    elif args.task == "migrate":
        directory = Path(args.directory)
        if (directory / "postgres.secret.json").exists():
            raise SystemExit(
                "PostgreSQL migrations require the explicit admin lifecycle command: python -m scripts.postgres migrate"
            )
        store = Store(directory / "observed/finance.db")
        with store.connect() as db:
            print(
                json.dumps(
                    {
                        "schema_version": db.execute(
                            "SELECT MAX(version) FROM schema_migrations"
                        ).fetchone()[0],
                        "path": store.path,
                    }
                )
            )
    elif args.task == "seed-demo":
        destination = Path("fixtures/golden.csv")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(csv_bytes(golden_rows()))
        print(f"Synthetic CSV written: {destination.resolve()}")
        directory = Path(args.directory)
        # A migration-only SQLite database is safe to initialize only when empty.
        db_path = directory / "observed/finance.db"
        if db_path.exists() and not (directory / "runtime.secret.json").exists():
            store = Store(db_path)
            with store.connect() as db:
                if db.execute("SELECT COUNT(*) FROM companies").fetchone()[0]:
                    raise SystemExit("Incomplete existing company workspace; refusing to reseed")
            with Runtime(directory, store=store):
                print("Synthetic company and independent world initialized; membership file saved.")
        else:
            with Runtime(directory, resume=True):
                print("Synthetic workspace ready; existing data retained.")
    else:
        print(
            "Stop the foreground server with Ctrl+C. Its sandbox child is stopped in finally; files are retained."
        )


if __name__ == "__main__":
    main()
