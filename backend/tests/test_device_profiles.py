from app.device_profiles import DEVICE_PROFILES, DESKTOP, MOBILE


def test_device_profiles_are_deterministic():
    assert DESKTOP.viewport_width == 1440
    assert DESKTOP.is_mobile is False
    assert MOBILE.viewport_width == 390
    assert MOBILE.is_mobile is True
    assert MOBILE.has_touch is True
    assert DEVICE_PROFILES["desktop"] == DESKTOP
    assert DEVICE_PROFILES["mobile"] == MOBILE
