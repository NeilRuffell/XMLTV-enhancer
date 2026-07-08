from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class FileCache:
    def __init__(self, cache_dir: Path, version: str) -> None:
        self.cache_dir = cache_dir
        self.version = version
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha256(f"{self.version}|{key}".encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        path = self._path_for(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, value: dict[str, Any]) -> None:
        path = self._path_for(key)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def clear(self) -> None:
        if not self.cache_dir.exists():
            return
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
