from shanten_sensei.features import (
    basic_danger_tags,
    build_score_situation,
    calculate_shanten,
    calculate_ukeire,
    classify_wait_shape,
    collect_visible_tiles,
    extract_features,
    hand_without_discard,
    wait_tiles_if_tenpai,
)


HAND = [
    "1m", "2m", "3m", "4m", "5m", "6m",
    "1p", "2p", "3p", "9p",
    "4s", "5s", "6s", "7s",
]


def test_mortal_discard_reaches_ryanmen_tenpai():
    assert calculate_shanten(HAND) == 0
    after = hand_without_discard(HAND, "9p")
    assert calculate_shanten(after) == 0
    waits = wait_tiles_if_tenpai(after)
    assert set(waits) == {"4s", "7s"}
    assert classify_wait_shape(waits) == "ryanmen"


def test_player_discard_falls_back_to_iishanten():
    after = hand_without_discard(HAND, "5s")
    assert calculate_shanten(after) == 1


def test_ukeire_after_mortal_discard():
    uke = calculate_ukeire(HAND, after_discard="9p")
    assert uke.count == 6
    assert set(uke.tiles) == {"4s", "7s"}
    assert uke.remaining_by_tile == {"4s": 3, "7s": 3}


def test_ukeire_visible_adjusted_depletes_waits():
    """Two 4s already in rivers → visible-adjusted count drops 6 → 4."""
    uke = calculate_ukeire(
        HAND,
        after_discard="9p",
        visible_tiles=["4s", "4s"],
    )
    assert uke.count == 4
    assert uke.remaining_by_tile == {"4s": 1, "7s": 3}


def test_ukeire_no_visible_matches_optimistic():
    assert calculate_ukeire(HAND, after_discard="9p").count == calculate_ukeire(
        HAND, after_discard="9p", visible_tiles=[]
    ).count


def test_collect_visible_tiles_prefers_rivers_over_discards():
    tiles = collect_visible_tiles(
        visible_discards={"0": ["1m"], "1": ["2p"]},
        discards=["9s"],  # ignored when rivers present
        dora_indicators=["4m"],
    )
    assert sorted(tiles) == ["1m", "2p", "4m"]


def test_extract_features_statuses():
    feats = extract_features(
        HAND,
        dora_indicators=["4m"],
        ukeire_after_discard="9p",
        genbutsu_tiles=["9p"],
        candidate_tiles=["9p", "5s"],
    )
    assert feats.statuses.menzen is True
    assert feats.statuses.tenpai is True
    assert feats.statuses.wait_shape == "ryanmen"
    assert "5m" in feats.statuses.dora_in_hand  # indicator 4m → dora 5m
    assert feats.danger.get("9p") == "genbutsu"
    # 4m indicator is not an improving tile → count still 6
    assert feats.ukeire.count == 6


def test_extract_features_visible_rivers_and_ukeire_alt():
    feats = extract_features(
        HAND,
        visible_discards={"1": ["4s", "4s"]},
        ukeire_after_discard="9p",
        ukeire_alt_after_discard="5s",
    )
    assert feats.ukeire.count == 4
    assert feats.ukeire.remaining_by_tile["4s"] == 1
    assert feats.ukeire_alt is not None
    assert feats.ukeire_alt.count != feats.ukeire.count


def test_danger_suji_from_river_discard():
    tags = basic_danger_tags(
        ["1m", "7m", "6m"],
        visible_discards={"1": ["4m"]},
    )
    assert tags.get("1m") == "suji"
    assert tags.get("7m") == "suji"
    assert "6m" not in tags


def test_danger_one_chance_from_visible_middle():
    tags = basic_danger_tags(
        ["4p", "6p", "2p"],
        visible_tiles=["5p", "5p", "5p"],
    )
    assert tags.get("4p") == "one-chance"
    assert tags.get("6p") == "one-chance"
    assert "2p" not in tags


def test_danger_genbutsu_beats_suji():
    tags = basic_danger_tags(
        ["1m"],
        visible_discards={"1": ["4m", "1m"]},
    )
    assert tags.get("1m") == "genbutsu"


def test_build_score_situation_trailing_late():
    sit = build_score_situation(
        scores=[20000, 28000, 25000, 27000],
        riichi_flags=[False, True, False, False],
        tiles_left=24,
        kyoku=3,
    )
    assert sit is not None
    assert sit.riichi_opponents == 1
    assert sit.score_diff == "trailing"
    assert sit.late_game is True


def test_build_score_situation_even_no_flags():
    sit = build_score_situation(scores=[25000, 25000, 25000, 25000])
    assert sit is not None
    assert sit.score_diff == "even"
    assert sit.riichi_opponents == 0
    assert sit.late_game is False
