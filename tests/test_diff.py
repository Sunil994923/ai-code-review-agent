from code_review_agent.diff import parse_unified_diff, select_reviewable


def test_parses_files_and_commentable_lines(sample_diff):
    files = {f.path: f for f in parse_unified_diff(sample_diff)}

    assert list(files) == ["app/payments.py", "package-lock.json", "old/legacy.py"]
    payments = files["app/payments.py"]
    # Hunk starts at new line 10: two context lines (10, 11), three added lines (12-14), context 15...
    assert {12, 13, 14} <= payments.commentable_lines
    assert {10, 11, 15} <= payments.commentable_lines
    assert payments.added_lines == 3


def test_patch_is_annotated_with_new_line_numbers(sample_diff):
    payments = next(f for f in parse_unified_diff(sample_diff) if f.path == "app/payments.py")

    assert "   12 +    query =" in payments.patch
    # Removed lines carry no number because they cannot receive inline comments.
    assert "      -    result = gateway.charge(customer.id, amount)" in payments.patch


def test_deleted_files_are_marked(sample_diff):
    deleted = [f for f in parse_unified_diff(sample_diff) if f.deleted]

    assert [f.path for f in deleted] == ["old/legacy.py"]
    assert deleted[0].added_lines == 0


def test_select_skips_lockfiles_and_deleted_files(sample_diff):
    selected, skipped = select_reviewable(parse_unified_diff(sample_diff))

    assert [f.path for f in selected] == ["app/payments.py"]
    assert skipped == []


def test_select_reports_files_over_budget(sample_diff):
    selected, skipped = select_reviewable(parse_unified_diff(sample_diff), max_chars=10)

    assert selected == []
    assert skipped == ["app/payments.py"]
