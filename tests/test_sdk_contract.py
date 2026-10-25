"""Runs the real Anthropic SDK against a mocked HTTP transport.

Verifies the request the SDK actually sends (model, schema, fallback header/body) and that a
JSON response is parsed into ReviewResult, without network access or an API key.
"""

import json

import anthropic
import httpx2

from code_review_agent.diff import parse_unified_diff, select_reviewable
from code_review_agent.llm import LlmReviewer
from code_review_agent.models import Severity

REVIEW_JSON = {
    "summary": "Adds a card lookup before charging.",
    "findings": [{
        "path": "app/payments.py", "line": 12, "severity": "critical", "category": "security",
        "title": "SQL injection", "explanation": "customer.id is interpolated into SQL.",
        "suggestion": "Use a parameterised query.",
    }],
}


def test_sdk_request_and_parsing(sample_diff):
    captured = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": json.dumps(REVIEW_JSON)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })

    client = anthropic.Anthropic(api_key="test", base_url="https://api.test",
                                 http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    files = select_reviewable(parse_unified_diff(sample_diff))[0]

    result = LlmReviewer(client=client).review(files, title="t")

    body = captured["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "server-side-fallback-2026-07-01" in captured["headers"]["anthropic-beta"]
    assert result.findings[0].severity is Severity.CRITICAL
    assert result.findings[0].line == 12
