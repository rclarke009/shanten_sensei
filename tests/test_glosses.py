from shanten_sensei.glosses import (
    DANGER_GLOSS,
    GOAL_GLOSS,
    NO_CLEAR_SHAPE,
    SHAPE_NOTE_GLOSS,
    WAIT_GLOSS,
    YAKU_REFERENCE_URL,
    format_aiming_for,
    glossed_danger,
    glossed_furiten,
    glossed_goal,
    glossed_shanten,
    glossed_wait,
)


def test_format_aiming_for_empty():
    assert format_aiming_for([]) == NO_CLEAR_SHAPE
    assert format_aiming_for(None) == NO_CLEAR_SHAPE


def test_format_aiming_for_single():
    assert format_aiming_for(["tanyao"]) == glossed_goal("tanyao")
    assert "2–8 only" in format_aiming_for(["tanyao"])


def test_format_aiming_for_multiple():
    line = format_aiming_for(["honitsu", "yakuhai"])
    assert "honitsu (one suit + winds/dragons OK)" in line
    assert "yakuhai (triplet of dragon or your seat/round wind)" in line
    assert " / " in line


def test_yakuhai_gloss_mentions_triplet():
    assert "triplet" in GOAL_GLOSS["yakuhai"]


def test_pinfu_ittsu_gloss():
    assert "sequences" in GOAL_GLOSS["pinfu"]
    assert "1–9" in GOAL_GLOSS["ittsu"] or "1-9" in GOAL_GLOSS["ittsu"]
    assert "pinfu" in format_aiming_for(["pinfu"])
    assert "ittsu" in format_aiming_for(["ittsu"])


def test_yaku_reference_url():
    assert YAKU_REFERENCE_URL.startswith("https://")
    assert "yaku" in YAKU_REFERENCE_URL.lower()


def test_wait_gloss_ryanmen():
    assert WAIT_GLOSS["ryanmen"] == "two-sided open"
    assert glossed_wait("ryanmen") == "ryanmen (two-sided open)"
    assert glossed_wait("kanchan") == "kanchan (closed middle)"
    assert glossed_wait(None) is None


def test_glossed_shanten():
    assert glossed_shanten(-1) == "complete (winning hand)"
    assert glossed_shanten(0) == "tenpai (ready)"
    assert glossed_shanten(1) == "1-shanten (1 step from ready)"
    assert glossed_shanten(3) == "3-shanten (3 steps from ready)"
    assert glossed_shanten(8) == "hand sync unavailable"
    assert "8-shanten" not in glossed_shanten(8)


def test_danger_gloss():
    assert "edge" in DANGER_GLOSS["suji"]
    assert "already" in DANGER_GLOSS["suji"]
    assert "middle tile" in DANGER_GLOSS["one-chance"]
    assert "unlikely" in DANGER_GLOSS["one-chance"]
    assert "edge" in glossed_danger("suji")
    assert "already discarded" in DANGER_GLOSS["genbutsu"]
    assert "can't ron" in DANGER_GLOSS["genbutsu"]
    assert glossed_danger("genbutsu") == (
        "genbutsu (safe — opponent already discarded it, so they can't ron it)"
    )
    assert glossed_danger(None) is None


def test_glossed_furiten():
    assert glossed_furiten() == "not furiten"
    assert "tsumo" in glossed_furiten(furiten=True).lower()
    assert "discard" in glossed_furiten(furiten=True).lower()
    assert "passed" in glossed_furiten(temporary=True).lower()


def test_shape_note_gloss():
    assert "lone 1/9" in SHAPE_NOTE_GLOSS["floating_terminal"]
    assert "closed middle" in SHAPE_NOTE_GLOSS["isolated_kanchan"]
    assert "dead-end" in SHAPE_NOTE_GLOSS["dead_end"] or "connects" in SHAPE_NOTE_GLOSS[
        "dead_end"
    ]
