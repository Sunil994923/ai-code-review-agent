import json

import httpx

from code_review_agent.github import API, GitHubClient
from code_review_agent.models import Category, Finding, Severity
from code_review_agent.review import ValidatedReview


def make_client(handler) -> GitHubClient:
    return GitHubClient("t0ken", http=httpx.Client(base_url=API, transport=httpx.MockTransport(handler)))


def test_get_pull_request_fetches_metadata_and_diff():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer t0ken"
        if request.headers["Accept"] == "application/vnd.github.diff":
            return httpx.Response(200, text="diff --git a/x b/x")
        return httpx.Response(200, json={"title": "T", "body": None, "head": {"sha": "abc123"}})

    pr = make_client(handler).get_pull_request("octo/repo", 7)

    assert (pr.title, pr.body, pr.head_sha, pr.diff) == ("T", "", "abc123", "diff --git a/x b/x")


def test_publish_review_posts_single_review_with_inline_comments():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": 99})

    finding = Finding(path="a.py", line=3, severity=Severity.MEDIUM, category=Category.BUG,
                      title="Off by one", explanation="Loop skips the last item.")
    review = ValidatedReview(summary="Summary", inline=[finding])

    review_id = make_client(handler).publish_review("octo/repo", 7, "abc123", review)

    assert review_id == 99
    assert captured["url"].endswith("/repos/octo/repo/pulls/7/reviews")
    body = captured["body"]
    assert body["commit_id"] == "abc123" and body["event"] == "COMMENT"
    assert body["comments"] == [{"path": "a.py", "line": 3, "side": "RIGHT",
                                 "body": body["comments"][0]["body"]}]
    assert "Off by one" in body["comments"][0]["body"]
