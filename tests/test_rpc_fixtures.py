"""Tests for the safe, sanitized RPC response shapes discovered on RP7 V2.0."""

MOTION = {
    "Enable": False,
    "HumanDetectFliter": True,
    "HumanTrack": True,
    "Level": 80,
}

GENERAL = {
    "hardVersion": "V2.0",
    "machineModel": "RP7V2.0",
    "machineSN": "REDACTED",
    "softVersion": "V21.7.18.99",
    "uuid": "REDACTED",
}


def test_rp7_fixture_has_expected_motion_keys() -> None:
    assert set(("Enable", "HumanDetectFliter", "HumanTrack")) <= MOTION.keys()


def test_rp7_fixture_has_expected_identity_keys() -> None:
    assert GENERAL["machineModel"] == "RP7V2.0"
    assert GENERAL["hardVersion"] == "V2.0"
