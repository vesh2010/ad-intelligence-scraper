from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    viewport_width: int
    viewport_height: int
    is_mobile: bool
    device_scale_factor: float = 1.0
    has_touch: bool = False


DESKTOP = DeviceProfile("desktop", 1440, 900, False)
MOBILE = DeviceProfile("mobile", 390, 844, True, 3.0, True)

DEVICE_PROFILES = {profile.name: profile for profile in (DESKTOP, MOBILE)}
