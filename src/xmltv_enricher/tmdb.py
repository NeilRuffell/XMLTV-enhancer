from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class TMDbClient:
    token: str
    language: str
    region: str
    base_url: str = "https://api.themoviedb.org/3"

    @property
    def available(self) -> bool:
        return bool(self.token.strip())

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    async def search_multi(self, query: str) -> list[dict[str, Any]]:
        if not self.available:
            return []
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{self.base_url}/search/multi",
                params={"query": query, "language": self.language, "region": self.region, "include_adult": "false"},
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()
        return [result for result in data.get("results", []) if result.get("media_type") in {"movie", "tv"}]
