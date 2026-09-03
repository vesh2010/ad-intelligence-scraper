from app.device_profiles import DESKTOP, MOBILE


def test_profiles_are_valid():
    assert (DESKTOP.viewport_width, DESKTOP.viewport_height) == (1440, 900)
    assert DESKTOP.is_mobile is False
    assert (MOBILE.viewport_width, MOBILE.viewport_height) == (390, 844)
    assert MOBILE.is_mobile is True
    assert MOBILE.has_touch is True
