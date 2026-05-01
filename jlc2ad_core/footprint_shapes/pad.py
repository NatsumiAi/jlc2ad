from typing import Optional

from ..types import EASYEDA_PAD_SHAPE, LAYER_MAP, PAD_SHAPE_RECT, PAD_SHAPE_ROUND, Pad, Region
from .context import FootprintParseContext
from .path import parse_path_points, parse_shape_payload


class PadHandler:
    shape_type = 'PAD'

    def parse(self, parts, context: FootprintParseContext) -> Optional[Pad] | tuple[Pad, list[Region]]:
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

        custom_points = self._custom_polygon_points(shape_name, parts)
        if hole_r <= 0 and custom_points:
            hotspot_size = context.size(2.3792)
            pad = Pad(
                x=context.x(cx),
                y=context.y(cy),
                size_x=hotspot_size,
                size_y=hotspot_size,
                hole_size=0,
                shape=PAD_SHAPE_ROUND,
                rotation=0.0,
                layer=layer,
                name=pad_number,
                plated=plated,
            )
            points = custom_points[:]
            if points[0] != points[-1]:
                points.append(points[0])
            region = Region(points=[(context.x(x), context.y(y)) for x, y in points], layer=layer)
            return pad, [region]

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

    @staticmethod
    def _custom_polygon_points(shape_name: str, parts) -> list[tuple[float, float]]:
        if 'POLY' not in (shape_name or '').upper():
            return []
        for part in parts:
            payload = parse_shape_payload(part)
            points = parse_path_points(payload)
            if len(points) >= 3:
                return points
            if isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[0], str) and payload[0].upper() == 'POLY':
                points = parse_path_points(payload[1])
                if len(points) >= 3:
                    return points
        return []


__all__ = ['PadHandler']
