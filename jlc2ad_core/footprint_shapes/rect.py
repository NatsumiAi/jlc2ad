from typing import List

from ..types import LAYER_MAP, Track
from .context import FootprintParseContext


class RectHandler:
    shape_type = 'RECT'

    def parse(self, parts, context: FootprintParseContext) -> List[Track]:
        layer = LAYER_MAP.get(int(parts[4]) if len(parts) > 4 and parts[4] else 3, 33)
        width = float(parts[5]) if len(parts) > 5 and parts[5] else 0.15
        x1 = float(parts[6])
        y1 = float(parts[7])
        x2 = float(parts[8]) if len(parts) > 8 and parts[8] else x1
        y2 = float(parts[9]) if len(parts) > 9 and parts[9] else y1
        points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        return _tracks_from_points(points, width, layer, context)


def _tracks_from_points(points, width: float, layer: int, context: FootprintParseContext) -> List[Track]:
    tracks: List[Track] = []
    for index in range(len(points) - 1):
        x1, y1 = points[index]
        x2, y2 = points[index + 1]
        tracks.append(Track(
            x1=context.x(x1),
            y1=context.y(y1),
            x2=context.x(x2),
            y2=context.y(y2),
            width=context.size(width),
            layer=layer,
        ))
    return tracks


__all__ = ['RectHandler', '_tracks_from_points']
