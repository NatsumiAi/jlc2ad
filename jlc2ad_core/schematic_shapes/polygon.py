from typing import List

from ..types import SchLine
from .context import SchematicParseContext


class PolygonHandler:
    shape_type = 'PG'

    def parse(self, parts, context: SchematicParseContext) -> List[SchLine]:
        coords_str = parts[1] if len(parts) > 1 else ''
        width = max(1, int(round(float(parts[3])))) if len(parts) > 3 and parts[3] else 1
        values = []
        for token in coords_str.strip().split():
            try:
                values.append(float(token))
            except ValueError:
                continue

        points = [(values[i], values[i + 1]) for i in range(0, len(values) - 1, 2)]
        if len(points) < 2:
            return []

        lines: List[SchLine] = []
        for index in range(len(points)):
            x1, y1 = points[index]
            x2, y2 = points[(index + 1) % len(points)]
            lines.append(SchLine(
                x1=context.x(x1),
                y1=context.y(y1),
                x2=context.x(x2),
                y2=context.y(y2),
                width=width,
            ))
        return lines


__all__ = ['PolygonHandler']
