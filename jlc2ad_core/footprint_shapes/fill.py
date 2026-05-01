from typing import List

from ..types import LAYER_MAP, Region
from .context import FootprintParseContext
from .path import parse_circle_payload, parse_path_points, parse_shape_payload


class FillHandler:
    shape_type = 'FILL'

    def parse(self, parts, context: FootprintParseContext) -> List[Region]:
        layer = LAYER_MAP.get(int(parts[4]) if len(parts) > 4 and parts[4] else 3, 33)
        payload = parse_shape_payload(parts[7] if len(parts) > 7 else '')
        if not isinstance(payload, list):
            return []

        regions: List[Region] = []
        for shape in payload:
            points = self._shape_points(shape)
            if len(points) < 3:
                continue
            if points[0] != points[-1]:
                points.append(points[0])
            regions.append(Region(
                points=[(context.x(x), context.y(y)) for x, y in points],
                layer=layer,
            ))
        return regions

    @staticmethod
    def _shape_points(shape) -> list[tuple[float, float]]:
        circle = parse_circle_payload(shape)
        if circle:
            cx, cy, radius = circle
            return _circle_points(cx, cy, radius)
        return parse_path_points(shape)


def _circle_points(cx: float, cy: float, radius: float, segments: int = 32) -> list[tuple[float, float]]:
    import math

    points = []
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    points.append(points[0])
    return points


__all__ = ['FillHandler']
