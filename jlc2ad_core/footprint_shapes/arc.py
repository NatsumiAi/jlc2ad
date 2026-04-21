from typing import Optional

from ..geometry import svg_arc_geometry
from ..svg_path import parse_svg_arc
from ..types import Arc, LAYER_MAP
from .context import FootprintParseContext


class ArcHandler:
    shape_type = 'ARC'

    def parse(self, parts, context: FootprintParseContext) -> Optional[Arc]:
        width = float(parts[1])
        layer = LAYER_MAP.get(int(parts[2]) if parts[2] else 3, 33)
        svg = (parts[4] if len(parts) > 4 else '').strip()
        arc_data = parse_svg_arc(svg)
        if not arc_data:
            return None
        sx, sy, rx, ry, large_arc, sweep, ex, ey = arc_data
        arc_geometry = svg_arc_geometry(sx, sy, rx, ry, large_arc, sweep, ex, ey)
        return Arc(
            center_x=context.x(arc_geometry.center_x),
            center_y=context.y(arc_geometry.center_y),
            radius=context.size(arc_geometry.radius),
            start_angle=arc_geometry.start_angle,
            end_angle=arc_geometry.end_angle,
            width=context.size(width),
            layer=layer,
        )


__all__ = ['ArcHandler']
