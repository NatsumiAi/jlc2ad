from typing import List

from ..svg_path import path_line_points
from ..types import SchLine
from .context import SchematicParseContext


class SvgPathLineHandler:
    shape_type = 'PT'

    def parse(self, parts, context: SchematicParseContext) -> List[SchLine]:
        if len(parts) < 2:
            return []
        width = max(1, int(round(float(parts[3])))) if len(parts) > 3 and parts[3] else 1
        return [
            SchLine(
                x1=context.x(start[0]),
                y1=context.y(start[1]),
                x2=context.x(end[0]),
                y2=context.y(end[1]),
                width=width,
            )
            for start, end in path_line_points(parts[1])
        ]


__all__ = ['SvgPathLineHandler']
