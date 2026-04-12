from __future__ import annotations
import os
import time
import httpx


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @classmethod
    def from_env(cls) -> GitHubClient:
        return cls(token=os.environ["GITHUB_TOKEN"])

    def get(self, path: str, params: dict | None = None) -> dict | list:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict | list:
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: dict | None = None) -> dict | list:
        return self._request("PATCH", path, json=json)

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        url = f"{self.BASE}{path}"
        response = httpx.request(method, url, headers=self._headers, **kwargs)
        self._handle_rate_limit(response)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    def _handle_rate_limit(self, response: httpx.Response) -> None:
        remaining = int(response.headers.get("x-ratelimit-remaining", 1))
        if remaining == 0:
            reset_at = int(response.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = max(0, reset_at - time.time()) + 1
            time.sleep(wait)
