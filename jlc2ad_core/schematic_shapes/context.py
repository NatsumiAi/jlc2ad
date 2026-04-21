from dataclasses import dataclass

from ..geometry import CoordinateTransformer


@dataclass(frozen=True)
class SchematicParseContext:
    origin_x: float
    origin_y: float
    coords: CoordinateTransformer

    def x(self, value: float) -> int:
        return self.coords.x(value, self.origin_x)

    def y(self, value: float) -> int:
        return self.coords.y(value, self.origin_y)


__all__ = ['SchematicParseContext']
