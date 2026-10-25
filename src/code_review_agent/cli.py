"""Command-line entry point.

    code-review-agent pr  --repo owner/name --pr 42      # review a GitHub PR and post the review
    code-review-agent diff changes.diff                   # review a local diff, print Markdown
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from .diff import parse_unified_diff, select_reviewable
from .llm import DEFAULT_MODEL, LlmReviewer, ReviewRefusedError
from .models import Severity
from .review import render_comment, render_summary, validate

log = logging.getLogger("code_review_agent")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    reviewer = LlmReviewer(model=args.model, effort=args.effort)
    min_severity = Severity(args.min_severity)

    try:
        if args.command == "diff":
            diff_text = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
            files, skipped = select_reviewable(parse_unified_diff(diff_text))
            if not files:
                print("Nothing to review.")
                return 0
            review = validate(reviewer.review(files), files, min_severity, skipped)
            print(render_summary(review))
            for f in review.inline:
                print(f"\n---\n`{f.path}:{f.line}`\n\n{render_comment(f)}")
            return 0

        from .github import GitHubClient

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            log.error("GITHUB_TOKEN is not set")
            return 2
        github = GitHubClient(token)
        pr = github.get_pull_request(args.repo, args.pr)
        files, skipped = select_reviewable(parse_unified_diff(pr.diff))
        if not files:
            log.info("No reviewable changes in PR #%s", args.pr)
            return 0
        log.info("Reviewing %d file(s) in %s#%s with %s", len(files), args.repo, args.pr, args.model)
        review = validate(reviewer.review(files, pr.title, pr.body), files, min_severity, skipped)
        if args.dry_run:
            print(render_summary(review))
            return 0
        review_id = github.publish_review(args.repo, args.pr, pr.head_sha, review)
        log.info("Posted review %s with %d inline comment(s)", review_id, len(review.inline))
        return 0
    except ReviewRefusedError as e:
        log.warning("Review declined: %s", e)
        return 0
    except Exception:
        log.exception("Review failed")
        return 1


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="code-review-agent", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=os.environ.get("REVIEW_MODEL", DEFAULT_MODEL))
    p.add_argument("--effort", default=os.environ.get("REVIEW_EFFORT", "high"),
                   choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--min-severity", default=os.environ.get("REVIEW_MIN_SEVERITY", "low"),
                   choices=[s.value for s in Severity])
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("pr", help="Review a GitHub pull request")
    pr.add_argument("--repo", required=True, help="owner/name")
    pr.add_argument("--pr", required=True, type=int)
    pr.add_argument("--dry-run", action="store_true", help="Print the review instead of posting it")
    d = sub.add_parser("diff", help="Review a unified diff file ('-' for stdin)")
    d.add_argument("file")
    return p


if __name__ == "__main__":
    sys.exit(main())
