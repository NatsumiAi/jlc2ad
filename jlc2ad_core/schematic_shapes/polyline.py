from typing import List

from ..types import SchLine
from .context import SchematicParseContext


class PolylineHandler:
    shape_type = 'PL'

    def parse(self, parts, context: SchematicParseContext) -> List[SchLine]:
        coords_str = parts[1] if len(parts) > 1 else ''
        width = max(1, int(round(float(parts[3])))) if len(parts) > 3 and parts[3] else 1
        coords = coords_str.strip().split(' ')
        lines: List[SchLine] = []
        for index in range(0, len(coords) - 2, 2):
            try:
                lines.append(SchLine(
                    x1=context.x(float(coords[index])),
                    y1=context.y(float(coords[index + 1])),
                    x2=context.x(float(coords[index + 2])),
                    y2=context.y(float(coords[index + 3])),
                    width=width,
                ))
            except (ValueError, IndexError):
                continue
        return lines


__all__ = ['PolylineHandler']
