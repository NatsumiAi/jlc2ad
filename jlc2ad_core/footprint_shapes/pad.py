from typing import Optional

from ..types import EASYEDA_PAD_SHAPE, LAYER_MAP, PAD_SHAPE_RECT, Pad
from .context import FootprintParseContext


class PadHandler:
    shape_type = 'PAD'

    def parse(self, parts, context: FootprintParseContext) -> Optional[Pad]:
        shape_name = parts[1]
        cx, cy = float(parts[2]), float(parts[3])
        width, height = float(parts[4]), float(parts[5])
        easyeda_layer = int(parts[6])
        pad_number = parts[8] if len(parts) > 8 else '1'
        hole_r = float(parts[9]) if len(parts) > 9 and parts[9] else 0
        rotation = float(parts[11]) if len(parts) > 11 and parts[11] else 0
        plated = True
        if len(parts) > 15 and parts[15]:
            plated = parts[15].upper() != 'N'

        layer = LAYER_MAP.get(easyeda_layer, 1)
        shape = EASYEDA_PAD_SHAPE.get(shape_name, PAD_SHAPE_RECT)
        if hole_r > 0 and easyeda_layer != 11:
            layer = 74

        return Pad(
            x=context.x(cx),
            y=context.y(cy),
            size_x=context.size(width),
            size_y=context.size(height),
            hole_size=context.size(hole_r * 2),
            shape=shape,
            rotation=rotation,
            layer=layer,
            name=pad_number,
            plated=plated,
        )


__all__ = ['PadHandler']
