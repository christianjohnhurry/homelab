import pytest

from kanana_banana.branching import branch_name, slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Add login flow", "add-login-flow"),
        ("Fix: the EXPORT bug!!", "fix-the-export-bug"),
        ("  spaces   everywhere  ", "spaces-everywhere"),
        ("snake_case and dots.too", "snake-case-and-dots-too"),
        ("Ünïcödé naïve café", "n-c-d-na-ve-caf"),
        ("v2 API -- 100% done", "v2-api-100-done"),
        ("!!!", ""),
    ],
)
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slug_cut_at_word_boundary():
    slug = slugify("refactor the board rendering pipeline for faster updates")
    assert slug == "refactor-the-board-rendering-pipeline"
    assert len(slug) <= 40


def test_slug_exact_fit_kept_whole():
    text = "a" * 19 + " " + "b" * 20  # 40 chars once slugified
    assert slugify(text) == "a" * 19 + "-" + "b" * 20


def test_slug_single_long_word_hard_cut():
    assert slugify("x" * 60) == "x" * 40


def test_slug_never_ends_with_dash():
    assert not slugify("word " * 20).endswith("-")


@pytest.mark.parametrize(
    ("key", "name", "expected"),
    [
        ("HML-42", "Add login flow", "hml-42-add-login-flow"),
        ("KB-7", "Fix: export", "kb-7-fix-export"),
        ("HML-3", "!!!", "hml-3"),
        ("LONGBOARDKEY-100", "Thing", "longboardkey-100-thing"),
    ],
)
def test_branch_name(key, name, expected):
    assert branch_name(key, name) == expected


def test_branch_name_has_no_type_prefix():
    assert "/" not in branch_name("HML-1", "feature: thing")
