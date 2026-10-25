"""Minimal GitHub REST client for reading a PR and publishing a review."""

from dataclasses import dataclass

import httpx

from .review import ValidatedReview, render_comment, render_summary

API = "https://api.github.com"


@dataclass
class PullRequest:
    title: str
    body: str
    head_sha: str
    diff: str


class GitHubClient:
    def __init__(self, token: str, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(base_url=API, timeout=30.0)
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get_pull_request(self, repo: str, number: int) -> PullRequest:
        meta = self._http.get(f"/repos/{repo}/pulls/{number}", headers=self._headers)
        meta.raise_for_status()
        data = meta.json()
        diff = self._http.get(f"/repos/{repo}/pulls/{number}",
                              headers={**self._headers, "Accept": "application/vnd.github.diff"})
        diff.raise_for_status()
        return PullRequest(title=data["title"], body=data.get("body") or "",
                           head_sha=data["head"]["sha"], diff=diff.text)

    def publish_review(self, repo: str, number: int, commit_sha: str, review: ValidatedReview) -> int:
        """Posts one review (summary + inline comments) so the PR gets a single notification."""
        payload = {
            "commit_id": commit_sha,
            "event": "COMMENT",
            "body": render_summary(review),
            "comments": [
                {"path": f.path, "line": f.line, "side": "RIGHT", "body": render_comment(f)}
                for f in review.inline
            ],
        }
        response = self._http.post(f"/repos/{repo}/pulls/{number}/reviews",
                                   headers=self._headers, json=payload)
        response.raise_for_status()
        return response.json()["id"]
