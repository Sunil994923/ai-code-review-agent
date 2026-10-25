from code_review_agent.diff import parse_unified_diff, select_reviewable
from code_review_agent.models import Category, Finding, ReviewResult, Severity
from code_review_agent.review import render_comment, render_summary, validate


def finding(line: int, severity: Severity = Severity.HIGH, path: str = "app/payments.py") -> Finding:
    return Finding(path=path, line=line, severity=severity, category=Category.SECURITY,
                   title="SQL injection", explanation="customer.id is interpolated into SQL.",
                   suggestion="Use a parameterised query.")


def files(sample_diff):
    return select_reviewable(parse_unified_diff(sample_diff))[0]


def test_findings_on_diff_lines_become_inline_comments(sample_diff):
    review = validate(ReviewResult(summary="s", findings=[finding(12)]), files(sample_diff))

    assert [f.line for f in review.inline] == [12]
    assert review.general == []


def test_findings_outside_diff_are_kept_in_summary(sample_diff):
    result = ReviewResult(summary="s", findings=[finding(500), finding(3, path="unknown.py")])

    review = validate(result, files(sample_diff))

    assert review.inline == []
    assert len(review.general) == 2


def test_min_severity_filters_and_orders_by_severity(sample_diff):
    result = ReviewResult(summary="s", findings=[
        finding(13, Severity.LOW), finding(14, Severity.MEDIUM), finding(12, Severity.CRITICAL)])

    review = validate(result, files(sample_diff), min_severity=Severity.MEDIUM)

    assert [f.severity for f in review.inline] == [Severity.CRITICAL, Severity.MEDIUM]


def test_render_comment_includes_severity_and_suggestion():
    text = render_comment(finding(12))

    assert "HIGH · security" in text
    assert "Use a parameterised query." in text


def test_render_summary_counts_and_lists_skipped_files(sample_diff):
    review = validate(ReviewResult(summary="Adds card lookup.", findings=[finding(12), finding(999)]),
                      files(sample_diff), skipped_files=["big/generated.py"])

    text = render_summary(review)

    assert "Adds card lookup." in text
    assert "high: 2" in text
    assert "`app/payments.py:999`" in text
    assert "`big/generated.py`" in text


def test_render_summary_without_findings():
    from code_review_agent.review import ValidatedReview

    assert "No issues found." in render_summary(ValidatedReview(summary="Looks good."))
