import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ArcGeometry:
    center_x: float
    center_y: float
    radius: float
    start_angle: float
    end_angle: float


class CoordinateTransformer:
    def __init__(self, scale: float = 1.0, invert_y: bool = True):
        self.scale = scale
        self.invert_y = invert_y

    def x(self, value: float, origin: float) -> int:
        return int(round((value - origin) * self.scale))

    def y(self, value: float, origin: float) -> int:
        result = int(round((value - origin) * self.scale))
        return -result if self.invert_y else result

    def size(self, value: float) -> int:
        return int(round(value * self.scale))


def svg_arc_center(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    cos_p = math.cos(math.radians(phi))
    sin_p = math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    d = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    if d == 0:
        return (x1 + x2) / 2, (y1 + y2) / 2
    sq = max(0, (rx * rx * ry * ry - d) / d) ** 0.5
    if fa == fs:
        sq = -sq
    cxp, cyp = sq * rx * y1p / ry, -sq * ry * x1p / rx
    return (
        cos_p * cxp - sin_p * cyp + (x1 + x2) / 2,
        sin_p * cxp + cos_p * cyp + (y1 + y2) / 2,
    )


def svg_arc_geometry(sx, sy, rx, ry, large_arc, sweep, ex, ey) -> ArcGeometry:
    radius = (rx + ry) / 2.0
    cx, cy = svg_arc_center(sx, sy, rx, ry, 0, large_arc, sweep, ex, ey)
    start_angle = math.degrees(math.atan2(-(sy - cy), sx - cx)) % 360
    end_angle = math.degrees(math.atan2(-(ey - cy), ex - cx)) % 360
    if sweep == 1:
        start_angle, end_angle = end_angle, start_angle
    return ArcGeometry(cx, cy, radius, start_angle, end_angle)


__all__ = ['ArcGeometry', 'CoordinateTransformer', 'svg_arc_center', 'svg_arc_geometry']
