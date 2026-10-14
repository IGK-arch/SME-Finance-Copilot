"""Administrative independent evaluator; never exposed as an agent tool."""

import argparse
import json
from pathlib import Path

from finance.domain import now
from finance.store import Store
from sandbox.world import World


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True)
    parser.add_argument("--output", default="artifacts/browser-evaluation.json")
    args = parser.parse_args()
    root = Path(args.directory)
    metadata = json.loads((root / "runtime.secret.json").read_text(encoding="utf-8"))
    pg_config = root / "postgres.secret.json"
    if pg_config.exists():
        from finance.postgres import PostgresStore

        store: Store = PostgresStore(
            json.loads(pg_config.read_text(encoding="utf-8"))["dsn"], root / "observed"
        )
    else:
        store = Store(root / "observed/finance.db")
    with store.connect() as db:
        policy = store.policy(db, metadata["tenant"])
        states = [
            dict(r)
            for r in db.execute(
                "SELECT action_id,status,idempotency_key FROM actions WHERE tenant_id=?",
                (metadata["tenant"],),
            )
        ]
        unknown_events = db.execute(
            "SELECT COUNT(*) FROM audit WHERE tenant_id=? AND event_type='action.unknown'",
            (metadata["tenant"],),
        ).fetchone()[0]
        workflows = [
            dict(r)
            for r in db.execute(
                "SELECT run_id,status FROM workflow_runs WHERE tenant_id=?", (metadata["tenant"],)
            )
        ]
    result = {
        "at": now(),
        "scope": "Independent evaluator over the actual persistent browser workspace",
        "evaluation": World(str(root / "private/world.db")).evaluate(
            metadata["tenant"], policy["reserve_minor"]
        ),
        "operations": states,
        "unknown_events": unknown_events,
        "workflows": workflows,
    }
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
