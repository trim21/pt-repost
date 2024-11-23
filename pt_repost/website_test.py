from pt_repost.website import pattern_hdr10, pattern_hdr10_plus


def test_match_hdr10():
    s = (
        "Dolby Vision, Version 1.0, "
        "Profile 8.1, "
        "dvhe.08.06, BL+RPU, no metadata compression, "
        "HDR10 compatible / SMPTE ST 2094 App 4, "
        "Version HDR10+ Profile B, HDR10+ Profile B compatible"
    )

    assert pattern_hdr10.search(s)
    assert pattern_hdr10_plus.search(s)
