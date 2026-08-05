from __future__ import annotations

import json
from pathlib import Path

from app.core.schemas import WorkoutManifest


def discover_manifest_files(data_root: Path) -> list[Path]:
    return sorted(path for path in data_root.rglob("*.json") if "manifest" in path.name.lower())


def load_workout_manifests(data_root: Path) -> list[WorkoutManifest]:
    manifest_files = discover_manifest_files(data_root)
    manifests: list[WorkoutManifest] = []
    for manifest_path in manifest_files:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifests.append(WorkoutManifest.model_validate(payload))
    return manifests

