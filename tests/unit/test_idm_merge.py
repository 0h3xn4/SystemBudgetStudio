"""The three-way merge keeps what the user changed and takes what the model changed (D-241)."""

from __future__ import annotations

from budget_core.idm.merge import ABSENT, MergeLog, changed_paths, merge3


def merged(old: object, new: object, cur: object) -> tuple[object, list[str]]:
    log = MergeLog()
    return merge3(old, new, cur, log), log.kept


def test_the_model_changed_and_the_file_is_as_imported() -> None:
    assert merged({"a": 1}, {"a": 2}, {"a": 1}) == ({"a": 2}, [])


def test_the_user_changed_and_the_model_did_not() -> None:
    assert merged({"a": 1}, {"a": 1}, {"a": 5}) == ({"a": 5}, [])


def test_both_changed_to_different_values_the_user_wins_and_it_is_reported() -> None:
    assert merged({"a": 1}, {"a": 2}, {"a": 3}) == ({"a": 3}, ["a"])


def test_both_changed_to_the_same_value() -> None:
    assert merged({"a": 1}, {"a": 2}, {"a": 2}) == ({"a": 2}, [])


def test_keys_are_merged_one_by_one() -> None:
    old = {"mass": 1.0, "name": "x", "bus": "main"}
    new = {"mass": 2.0, "name": "y", "bus": "main"}  # the model changed mass and name
    cur = {"mass": 1.0, "name": "mine", "bus": "aux"}  # the user changed name and bus
    result, kept = merged(old, new, cur)
    assert result == {"mass": 2.0, "name": "mine", "bus": "aux"}
    assert kept == ["name"]


def test_what_only_the_user_has_is_kept() -> None:
    result, _ = merged({"a": 1}, {"a": 2}, {"a": 1, "extra": 7})
    assert result == {"a": 2, "extra": 7}


def test_a_key_the_model_added_is_added_and_one_it_dropped_goes_if_untouched() -> None:
    assert merged({"a": 1}, {"a": 1, "b": 2}, {"a": 1})[0] == {"a": 1, "b": 2}
    assert merged({"a": 1, "b": 2}, {"a": 1}, {"a": 1, "b": 2})[0] == {"a": 1}
    # ... but not when the user edited it
    result, kept = merged({"a": 1, "b": 2}, {"a": 1}, {"a": 1, "b": 9})
    assert result == {"a": 1, "b": 9} and kept == ["b"]


def modes(*items: tuple[str, float]) -> list[dict[str, object]]:
    return [{"name": n, "avg": v} for n, v in items]


def test_lists_of_named_items_are_merged_by_name() -> None:
    old = modes(("On", 10.0), ("Off", 0.0))
    new = modes(("On", 12.0), ("Off", 0.0), ("Idle", 1.0))
    cur = modes(("On", 10.0), ("Off", 0.0), ("Mine", 5.0))
    result, kept = merged(old, new, cur)
    assert result == modes(("On", 12.0), ("Off", 0.0), ("Idle", 1.0), ("Mine", 5.0))
    assert kept == []


def test_a_named_item_the_model_dropped_stays_when_the_user_edited_it() -> None:
    old = modes(("On", 10.0), ("Old", 3.0))
    new = modes(("On", 10.0))
    assert merged(old, new, modes(("On", 10.0), ("Old", 3.0)))[0] == modes(("On", 10.0))
    result, kept = merged(old, new, modes(("On", 10.0), ("Old", 4.0)))
    assert result == modes(("On", 10.0), ("Old", 4.0)) and kept == ["[Old]"]


def test_plain_lists_are_atomic() -> None:
    assert merged(["a"], ["a", "b"], ["a"])[0] == ["a", "b"]
    result, kept = merged(["a"], ["a", "b"], ["z"])
    assert result == ["z"] and kept == [""]


def test_absent_values() -> None:
    assert merge3(ABSENT, {"a": 1}, ABSENT, MergeLog()) == {"a": 1}
    assert merge3(ABSENT, ABSENT, {"a": 1}, MergeLog()) == {"a": 1}
    assert merge3({"a": 1}, ABSENT, {"a": 1}, MergeLog()) is ABSENT


def test_changed_paths_names_the_values_that_differ() -> None:
    before = {"mass": 1.0, "modes": modes(("On", 10.0)), "k": {"x": 1}}
    after = {"mass": 2.0, "modes": modes(("On", 11.0), ("Off", 0.0)), "k": {"x": 1}}
    assert changed_paths(before, after) == ["mass", "modes[Off]", "modes[On].avg"]
    assert changed_paths(before, before) == []
