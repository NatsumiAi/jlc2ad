from typing import Optional

from ..geometry import svg_arc_geometry
from ..svg_path import parse_svg_arc
from ..types import SchArc
from .context import SchematicParseContext


class ArcPathHandler:
    shape_type = 'A'

    def parse(self, parts, context: SchematicParseContext) -> Optional[SchArc]:
        if len(parts) < 2:
            return None
        arc_data = parse_svg_arc(parts[1])
        if not arc_data:
            return None

        sx, sy, rx, ry, large_arc, sweep, ex, ey = arc_data
        width = max(1, int(round(float(parts[4])))) if len(parts) > 4 and parts[4] else 1
        arc_geometry = svg_arc_geometry(sx, sy, rx, ry, large_arc, sweep, ex, ey)
        return SchArc(
            cx=context.x(arc_geometry.center_x),
            cy=context.y(arc_geometry.center_y),
            radius=int(round(rx)),
            start_angle=arc_geometry.start_angle,
            end_angle=arc_geometry.end_angle,
            width=width,
        )


__all__ = ['ArcPathHandler']
