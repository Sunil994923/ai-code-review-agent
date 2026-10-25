"""Orchestration: validate model findings against the diff and render them for GitHub."""

from dataclasses import dataclass, field

from .diff import FileDiff
from .models import Finding, ReviewResult, Severity

SEVERITY_ICON = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
}


@dataclass
class ValidatedReview:
    summary: str
    inline: list[Finding] = field(default_factory=list)
    # Findings the model placed on lines outside the diff; kept in the summary, not dropped.
    general: list[Finding] = field(default_factory=list)
    skipped_files: list[str] = field(default_factory=list)


def validate(result: ReviewResult, files: list[FileDiff], min_severity: Severity = Severity.LOW,
             skipped_files: list[str] | None = None) -> ValidatedReview:
    commentable = {f.path: f.commentable_lines for f in files}
    review = ValidatedReview(summary=result.summary, skipped_files=skipped_files or [])
    for finding in sorted(result.findings, key=lambda f: (f.severity.rank, f.path, f.line)):
        if finding.severity.rank > min_severity.rank:
            continue
        if finding.line in commentable.get(finding.path, set()):
            review.inline.append(finding)
        else:
            review.general.append(finding)
    return review


def render_comment(finding: Finding) -> str:
    label = f"{finding.severity.value.upper()} · {finding.category.value}"
    lines = [f"{SEVERITY_ICON[finding.severity]} **{label}** — {finding.title}", "", finding.explanation]
    if finding.suggestion:
        lines += ["", "**Suggestion:**", finding.suggestion]
    return "\n".join(lines)


def render_summary(review: ValidatedReview) -> str:
    total = len(review.inline) + len(review.general)
    counts = {s: 0 for s in Severity}
    for f in review.inline + review.general:
        counts[f.severity] += 1
    out = ["## 🤖 AI code review", "", review.summary, ""]
    if total:
        out.append(" · ".join(f"{SEVERITY_ICON[s]} {s.value}: {n}" for s, n in counts.items() if n))
    else:
        out.append("No issues found.")
    if review.general:
        out += ["", "### Findings outside the diff", ""]
        out += [f"- `{f.path}:{f.line}` {SEVERITY_ICON[f.severity]} **{f.title}** — {f.explanation}"
                for f in review.general]
    if review.skipped_files:
        out += ["", "<details><summary>Files not reviewed (size limit)</summary>", ""]
        out += [f"- `{p}`" for p in review.skipped_files]
        out += ["", "</details>"]
    out += ["", "<sub>Automated review. Treat findings as suggestions and verify before applying.</sub>"]
    return "\n".join(out)
