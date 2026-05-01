from typing import List

from ..types import Arc, LAYER_MAP, Track
from .context import FootprintParseContext
from .path import parse_circle_payload, parse_path_points, parse_shape_payload
from .rect import _tracks_from_points


class PolyHandler:
    shape_type = 'POLY'

    def parse(self, parts, context: FootprintParseContext) -> tuple[List[Track], List[Arc]]:
        layer = LAYER_MAP.get(int(parts[4]) if len(parts) > 4 and parts[4] else 3, 33)
        width = float(parts[5]) if len(parts) > 5 and parts[5] else 0.15
        payload = parse_shape_payload(parts[6] if len(parts) > 6 else '')
        circle = parse_circle_payload(payload)
        if circle:
            cx, cy, radius = circle
            return [], [Arc(
                center_x=context.x(cx),
                center_y=context.y(cy),
                radius=context.size(radius),
                start_angle=0.0,
                end_angle=360.0,
                width=context.size(width),
                layer=layer,
            )]

        points = parse_path_points(payload)
        if len(points) < 2:
            return [], []
        return _tracks_from_points(points, width, layer, context), []


__all__ = ['PolyHandler']
