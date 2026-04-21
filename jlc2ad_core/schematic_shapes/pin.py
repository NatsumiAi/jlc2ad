from typing import Optional

from ..svg_path import pin_length_from_path
from ..types import SchPin
from .context import SchematicParseContext


class PinHandler:
    shape_type = 'P'

    def __init__(self, electrical_map: dict):
        self.electrical_map = electrical_map

    def parse(self, parts, context: SchematicParseContext) -> Optional[SchPin]:
        if len(parts) < 7:
            return None
        electric_str = parts[2] if len(parts) > 2 else '0'
        header_number = parts[3] if len(parts) > 3 else ''
        px = float(parts[4]) if len(parts) > 4 else 0
        py = float(parts[5]) if len(parts) > 5 else 0
        rotation = float(parts[6]) if len(parts) > 6 else 0

        subsections = '~'.join(parts).split('^^')
        pin_number = header_number
        pin_name = header_number
        for section_index in (3, 4):
            if len(subsections) > section_index:
                fields = subsections[section_index].split('~')
                if len(fields) > 4:
                    text = fields[4].strip()
                    if text and text != header_number:
                        pin_name = text
                        break

        pin_length = 20
        if len(subsections) >= 3:
            pin_length = pin_length_from_path(subsections[2].strip(), default=20)

        orientation = {0: 2, 90: 3, 180: 0, 270: 1}.get(int(rotation) % 360, 0)
        electrical = self.electrical_map.get(electric_str, 4)
        return SchPin(
            x=context.x(px),
            y=context.y(py),
            length=max(pin_length, 5),
            orientation=orientation,
            name=pin_name,
            number=pin_number,
            electrical=electrical,
        )


__all__ = ['PinHandler']
