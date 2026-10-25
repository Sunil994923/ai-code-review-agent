"""Unified-diff parsing.

GitHub only accepts inline review comments on lines that appear in the diff, so we record,
for every file, which new-side line numbers are commentable.
"""

import fnmatch
import re
from dataclasses import dataclass, field

HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

DEFAULT_IGNORED = (
    "*.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "*.min.js", "*.min.css", "*.map", "*.svg", "*.png", "*.jpg", "*.gif", "*.pdf",
    "dist/*", "build/*", "vendor/*", "node_modules/*",
)


@dataclass
class FileDiff:
    path: str
    patch: str
    commentable_lines: set[int] = field(default_factory=set)
    added_lines: int = 0
    deleted: bool = False


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    """Split a `git diff` / GitHub `.diff` payload into per-file diffs."""
    files: list[FileDiff] = []
    current: FileDiff | None = None
    patch_lines: list[str] = []
    new_line = 0
    old_path = ""

    def flush() -> None:
        if current is not None:
            current.patch = "\n".join(patch_lines)
            files.append(current)

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            flush()
            current, patch_lines, new_line, old_path = None, [], 0, ""
            continue
        if current is None and raw.startswith("--- "):
            old_path = _strip_prefix(raw[4:].strip(), "a/")
            continue
        if current is None and raw.startswith("+++ "):
            target = raw[4:].strip()
            deleted = target == "/dev/null"
            current = FileDiff(path=old_path if deleted else _strip_prefix(target, "b/"), patch="",
                               deleted=deleted)
            continue
        if current is None:
            continue  # file headers (index, ---, mode lines) before +++
        header = HUNK_HEADER.match(raw)
        if header:
            new_line = int(header.group(1))
            patch_lines.append(raw)
            continue
        if raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        if raw.startswith("+"):
            current.commentable_lines.add(new_line)
            current.added_lines += 1
            patch_lines.append(f"{new_line:>5} {raw}")
            new_line += 1
        elif raw.startswith("-"):
            patch_lines.append(f"{'':>5} {raw}")
        else:
            current.commentable_lines.add(new_line)
            patch_lines.append(f"{new_line:>5} {raw}")
            new_line += 1
    flush()
    return files


def _strip_prefix(path: str, prefix: str) -> str:
    return path[len(prefix):] if path.startswith(prefix) else path


def select_reviewable(files: list[FileDiff], ignore: tuple[str, ...] = DEFAULT_IGNORED,
                      max_chars: int = 120_000) -> tuple[list[FileDiff], list[str]]:
    """Drop deleted/generated files and stop before the prompt budget is exceeded.

    Returns the files to review and the paths that were skipped (reported in the summary
    rather than silently truncated).
    """
    selected: list[FileDiff] = []
    skipped: list[str] = []
    used = 0
    for f in files:
        if f.deleted or f.added_lines == 0 or any(fnmatch.fnmatch(f.path, p) for p in ignore):
            continue
        if used + len(f.patch) > max_chars:
            skipped.append(f.path)
            continue
        selected.append(f)
        used += len(f.patch)
    return selected, skipped
