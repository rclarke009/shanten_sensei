from shanten_sensei.features import (
    calculate_shanten,
    calculate_ukeire,
    classify_wait_shape,
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
