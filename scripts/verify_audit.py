from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from finance.store import Store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=".runtime/workspace")
    args = parser.parse_args()
    directory = Path(args.directory)
    tokens = json.loads((directory / "local-login.secret.json").read_text(encoding="utf-8"))
    pg_config = directory / "postgres.secret.json"
    if pg_config.exists():
        from finance.postgres import PostgresStore

        config = json.loads(pg_config.read_text(encoding="utf-8"))
        store: Store = PostgresStore(config["dsn"], directory / "observed")
    else:
        db_path = directory / "observed/finance.db"
        if not db_path.exists():
            print(f"No workspace database at {db_path}", file=sys.stderr)
            return 2
        store = Store(db_path)
    result = store.verify_audit(store.authenticate(tokens["AUDITOR"]))
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
