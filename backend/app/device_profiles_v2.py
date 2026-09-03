from dataclasses import dataclass

@dataclass(frozen=True)
class DeviceProfile:
    name: str
    viewport_width: int
    viewport_height: int
    is_mobile: bool
    device_scale_factor: float
    has_touch: bool

DESKTOP=DeviceProfile('desktop',1440,900,False,1.0,False)
MOBILE=DeviceProfile('mobile',390,844,True,3.0,True)
