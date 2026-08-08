"""Chi meld enumeration for skip/call coaching."""

from shanten_sensei.tiles import chi_meld_label, enumerate_chi_melds

# diverge_005 hand shape: chi 5mr with 4m+6m → 4-5-6 man
DIVERGE_005_HAND = [
    "4m",
    "6m",
    "2p",
    "4p",
    "6p",
    "8p",
    "2s",
    "3s",
    "6s",
    "7s",
    "W",
    "W",
    "C",
]

# Screenshot-shaped hand: chi 7s as 6-7-8 or 7-8-9 sou
SCREENSHOT_HAND = [
    "4m",
    "7m",
    "8m",
    "9m",
    "2s",
    "3s",
    "4s",
    "6s",
    "8s",
    "9s",
    "8p",
    "8p",
    "9p",
]


def test_enumerate_single_chi_meld():
    melds = enumerate_chi_melds(DIVERGE_005_HAND, "5mr")
    assert melds == [("4m", "5m", "6m")]


def test_chi_meld_label_red_five():
    assert chi_meld_label(("4m", "5m", "6m")) == "4-5-6 man"


def test_enumerate_double_chi_meld():
    melds = enumerate_chi_melds(SCREENSHOT_HAND, "7s")
    assert melds == [("6s", "7s", "8s"), ("7s", "8s", "9s")]
    assert chi_meld_label(melds[0]) == "6-7-8 sou"
    assert chi_meld_label(melds[1]) == "7-8-9 sou"


def test_enumerate_chi_honor_discard():
    assert enumerate_chi_melds(SCREENSHOT_HAND, "W") == []


def test_enumerate_chi_impossible_discard():
    assert enumerate_chi_melds(SCREENSHOT_HAND, "9s") == []
