from typing import List

from ..types import LAYER_MAP, Track
from .context import FootprintParseContext


class TrackHandler:
    shape_type = 'TRACK'

    def parse(self, parts, context: FootprintParseContext) -> List[Track]:
        width = float(parts[1])
        layer = LAYER_MAP.get(int(parts[2]) if parts[2] else 3, 33)
        coords = (parts[4] if len(parts) > 4 else '').strip().split(' ')
        tracks: List[Track] = []
        for index in range(0, len(coords) - 2, 2):
            try:
                tracks.append(Track(
                    x1=context.x(float(coords[index])),
                    y1=context.y(float(coords[index + 1])),
                    x2=context.x(float(coords[index + 2])),
                    y2=context.y(float(coords[index + 3])),
                    width=context.size(width),
                    layer=layer,
                ))
            except (ValueError, IndexError):
                continue
        return tracks


__all__ = ['TrackHandler']
