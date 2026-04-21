from typing import Optional

from ..types import SchRect
from .context import SchematicParseContext


class RectHandler:
    shape_type = 'R'

    def parse(self, parts, context: SchematicParseContext) -> Optional[SchRect]:
        if len(parts) < 7:
            return None
        try:
            x, y = float(parts[1]), float(parts[2])
            width, height = float(parts[5]), float(parts[6])
            stroke_width = max(1, int(round(float(parts[8])))) if len(parts) > 8 and parts[8] else 1
            return SchRect(
                x1=context.x(x),
                y1=context.y(y),
                x2=context.x(x + width),
                y2=context.y(y + height),
                width=stroke_width,
            )
        except (ValueError, IndexError):
            return None


__all__ = ['RectHandler']
