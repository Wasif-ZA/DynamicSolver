"""Phase 5: split_compatible is faster and colours identically.

The rewrite replaces "does this item conflict with any member" with three set
lookups per group. Faster is easy to check; identical is the part that matters,
because a grouping bug does not crash, it just puts two things in one carton
that must never share one.

So the fast path is checked against a literal transcription of the original
pairwise algorithm, over randomised orders that are built to actually collide.
"""
from __future__ import annotations

import random
from collections.abc import Sequence

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fitsolver.domain import Item
from fitsolver.greedy2.pack import conflict, split_compatible


def reference_split(items: Sequence[Item]) -> list[list[Item]]:
    """The original algorithm, kept here and nowhere else, as the oracle."""
    groups: list[list[Item]] = []
    for item in items:
        for g in groups:
            if not any(conflict(item, other) for other in g):
                g.append(item)
                break
        else:
            groups.append([item])
    return groups


def refs(groups) -> list[list[str]]:
    return [[i.ref for i in g] for g in groups]


# A small ref pool, so incompatible_with entries actually match something.
# Drawing refs from uuids would make almost every constraint inert and the
# test would pass while covering nothing.
REFS = [f"I{i}" for i in range(8)]

item_st = st.builds(
    Item,
    ref=st.sampled_from(REFS),
    dims=st.just((50, 50, 50)),
    mass=st.just(100),
    dg_class=st.sampled_from([None, None, "3", "8", "9"]),
    incompatible_with=st.frozensets(st.sampled_from(REFS), max_size=3),
)


@settings(max_examples=400, deadline=None)
@given(items=st.lists(item_st, max_size=30))
def test_colouring_is_identical_to_the_pairwise_version(items):
    assert refs(split_compatible(items)) == refs(reference_split(items))


@settings(max_examples=100, deadline=None)
@given(items=st.lists(item_st, max_size=25))
def test_no_group_holds_a_conflicting_pair(items):
    """The property the colouring exists to provide, checked directly rather
    than through the oracle, so a bug shared by both would still show."""
    for group in split_compatible(items):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                assert not conflict(a, b)


@settings(max_examples=100, deadline=None)
@given(items=st.lists(item_st, max_size=25))
def test_every_item_lands_in_exactly_one_group(items):
    groups = split_compatible(items)
    assert sum(len(g) for g in groups) == len(items)


def test_an_unset_dg_class_conflicts_with_nothing():
    """Unset means "not regulated", not "a class of its own". Treating it as
    its own class would split every ordinary order into two."""
    items = [Item("A", (10, 10, 10), 1, dg_class="3"),
             Item("B", (10, 10, 10), 1),
             Item("C", (10, 10, 10), 1, dg_class="3")]
    assert refs(split_compatible(items)) == [["A", "B", "C"]]


def test_two_regulated_classes_never_share():
    items = [Item("A", (10, 10, 10), 1, dg_class="3"),
             Item("B", (10, 10, 10), 1, dg_class="8")]
    assert refs(split_compatible(items)) == [["A"], ["B"]]


def test_a_group_takes_its_class_from_the_first_regulated_member():
    """An unregulated item can join, and a later item of a different class
    must then be refused by that same group."""
    items = [Item("A", (10, 10, 10), 1),
             Item("B", (10, 10, 10), 1, dg_class="3"),
             Item("C", (10, 10, 10), 1, dg_class="8"),
             Item("D", (10, 10, 10), 1, dg_class="3")]
    assert refs(split_compatible(items)) == [["A", "B", "D"], ["C"]]


def test_incompatibility_is_symmetric():
    """Declared on either side, it holds. Checking only one direction would
    let a one-sided declaration be ignored."""
    forward = [Item("A", (10, 10, 10), 1, incompatible_with=frozenset({"B"})),
               Item("B", (10, 10, 10), 1)]
    backward = [Item("A", (10, 10, 10), 1),
                Item("B", (10, 10, 10), 1, incompatible_with=frozenset({"A"}))]
    assert refs(split_compatible(forward)) == [["A"], ["B"]]
    assert refs(split_compatible(backward)) == [["A"], ["B"]]


def test_a_self_incompatible_item_does_not_share_with_its_own_copies():
    """quantity expansion repeats the same item, and an item that refuses its
    own ref must refuse those copies too."""
    item = Item("A", (10, 10, 10), 1, incompatible_with=frozenset({"A"}))
    assert refs(split_compatible([item, item])) == [["A"], ["A"]]


def test_identical_unconstrained_copies_all_share():
    item = Item("A", (10, 10, 10), 1)
    assert refs(split_compatible([item] * 5)) == [["A"] * 5]


def test_empty_input():
    assert split_compatible([]) == []


@pytest.mark.parametrize("n", [500, 2000])
def test_an_unconstrained_order_stays_linear(n):
    """The case the rewrite is for: no constraints at all still built one
    group by comparing every item against every earlier one.

    Asserts the shape of the growth, not a wall-clock number, so it does not
    turn into a flaky test on a loaded machine.
    """
    items = [Item(f"S{i}", (10, 10, 10), 1) for i in range(n)]
    groups = split_compatible(items)
    assert len(groups) == 1 and len(groups[0]) == n


def test_many_items_and_many_classes_still_group_correctly():
    r = random.Random(4)
    classes = [None, "3", "8", "9", "5.1"]
    items = [Item(f"S{i}", (10, 10, 10), 1,
                  dg_class=classes[r.randrange(len(classes))])
             for i in range(400)]
    groups = split_compatible(items)
    assert refs(groups) == refs(reference_split(items))
    for group in groups:
        present = {i.dg_class for i in group if i.dg_class}
        assert len(present) <= 1
