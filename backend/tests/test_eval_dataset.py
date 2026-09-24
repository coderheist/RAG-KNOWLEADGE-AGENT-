"""The golden dataset must be structurally sound and every gold evidence string must exist in exactly one document."""
from collections import Counter

from evals.dataset import CATEGORIES, load_dataset, validate


def test_golden_v1_has_no_validation_problems() -> None:
    problems = validate(load_dataset("golden_v1"))
    assert problems == [], "\n".join(problems)


def test_golden_v1_covers_every_category_with_enough_cases() -> None:
    rows = load_dataset("golden_v1")
    counts = Counter(r["category"] for r in rows)
    assert set(counts) == CATEGORIES
    assert len(rows) >= 60
    assert all(n >= 5 for n in counts.values()), counts
