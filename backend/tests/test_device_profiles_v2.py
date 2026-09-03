from app.device_profiles import DESKTOP, MOBILE


def test_profiles():
    assert (DESKTOP.viewport_width, DESKTOP.viewport_height, DESKTOP.is_mobile) == (1440, 900, False)
    assert (MOBILE.viewport_width, MOBILE.viewport_height, MOBILE.is_mobile, MOBILE.has_touch) == (390, 844, True, True)
