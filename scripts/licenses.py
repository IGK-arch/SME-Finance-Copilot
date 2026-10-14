"""Inventory installed distribution metadata; UNKNOWN remains unknown."""

import importlib.metadata
import json
from pathlib import Path

from finance.domain import now


def main() -> None:
    packages = []
    for line in Path("requirements.lock").read_text(encoding="utf-8-sig").splitlines():
        if "==" not in line or line.startswith("#"):
            continue
        name, pinned = line.split("==")
        distribution = importlib.metadata.distribution(name)
        metadata = distribution.metadata
        packages.append(
            {
                "name": name,
                "locked_version": pinned,
                "installed_version": distribution.version,
                "license_expression": metadata["License-Expression"] or "UNKNOWN",
                "license_field": metadata["License"] or "UNKNOWN",
                "declared_license_files": metadata.get_all("License-File") or [],
                "project_urls": metadata.get_all("Project-URL") or [],
                "scope": "Installed metadata only; no independent legal interpretation",
            }
        )
    Path("artifacts/dependency-inventory.json").write_text(
        json.dumps(
            {
                "at": now(),
                "packages": packages,
                "model_weights": [],
                "model_license_status": "NOT_APPLICABLE_NO_WEIGHTS_DOWNLOADED",
                "external_datasets": [],
                "handoff_rights": "UNKNOWN_OWNER_REVIEW_REQUIRED",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Inventoried {len(packages)} installed distributions; missing metadata remains UNKNOWN.")


if __name__ == "__main__":
    main()
