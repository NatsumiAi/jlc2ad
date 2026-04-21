from typing import Optional

from ..types import SchArc
from .context import SchematicParseContext


class EllipseHandler:
    shape_type = 'E'

    def parse(self, parts, context: SchematicParseContext) -> Optional[SchArc]:
        if len(parts) < 5:
            return None
        cx, cy = float(parts[1]), float(parts[2])
        rx = float(parts[3])
        width = max(1, int(round(float(parts[6])))) if len(parts) > 6 and parts[6] else 1
        return SchArc(
            cx=context.x(cx),
            cy=context.y(cy),
            radius=int(round(rx)),
            start_angle=0.0,
            end_angle=360.0,
            width=width,
        )


__all__ = ['EllipseHandler']
