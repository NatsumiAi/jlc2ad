from ..types import Arc, LAYER_MAP
from .context import FootprintParseContext


class CircleHandler:
    shape_type = 'CIRCLE'

    def parse(self, parts, context: FootprintParseContext) -> Arc:
        cx, cy = float(parts[1]), float(parts[2])
        radius = float(parts[3])
        width = float(parts[4]) if len(parts) > 4 and parts[4] else 0.15
        layer = LAYER_MAP.get(int(parts[5]) if len(parts) > 5 and parts[5] else 3, 33)
        return Arc(
            center_x=context.x(cx),
            center_y=context.y(cy),
            radius=context.size(radius),
            start_angle=0.0,
            end_angle=360.0,
            width=context.size(width),
            layer=layer,
        )


__all__ = ['CircleHandler']
