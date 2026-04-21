from typing import Optional

from .geometry import CoordinateTransformer
from .schematic_shapes import ArcPathHandler, EllipseHandler, PinHandler, PolygonHandler, PolylineHandler, RectHandler, SchematicParseContext, SvgPathLineHandler
from .types import SchSymbol


class SchematicParser:
    """解析 EasyEDA 原理图 shape 数据 → SchSymbol"""

    ELEC_MAP = {
        '0': 4,
        '1': 0,
        '2': 2,
        '3': 1,
        '4': 4,
    }

    def __init__(self):
        self.coords = CoordinateTransformer(scale=1.0, invert_y=True)
        self.single_handlers = {
            'P': PinHandler(self.ELEC_MAP),
            'R': RectHandler(),
            'E': EllipseHandler(),
            'A': ArcPathHandler(),
        }
        self.multi_handlers = {
            'PL': PolylineHandler(),
            'PG': PolygonHandler(),
            'PT': SvgPathLineHandler(),
        }

    def parse(self, component_data: dict) -> Optional[SchSymbol]:
        ds = component_data.get('sch_dataStr', {})
        if not ds:
            return None
        head = ds.get('head', {})
        origin_x = float(head.get('x', 0))
        origin_y = float(head.get('y', 0))

        c_para = head.get('c_para', {})

        sym = SchSymbol(
            name=component_data.get('title', 'Unknown'),
            designator=component_data.get('designator', 'U?'),
            description=component_data.get('description', ''),
            comment=component_data.get('lcsc_id', ''),
            package=c_para.get('package', ''),
            manufacturer=c_para.get('Manufacturer', ''),
            value=c_para.get('Value', ''),
            supplier_part=c_para.get('Supplier Part', ''),
            supplier='LCSC',
        )

        context = SchematicParseContext(origin_x=origin_x, origin_y=origin_y, coords=self.coords)

        for shape_str in ds.get('shape', []):
            parts = shape_str.split('~')
            shape_type = parts[0]
            try:
                if shape_type in self.single_handlers:
                    shape = self.single_handlers[shape_type].parse(parts, context)
                    if shape_type == 'P' and shape:
                        sym.pins.append(shape)
                    elif shape_type == 'R' and shape:
                        sym.rects.append(shape)
                    elif shape:
                        sym.arcs.append(shape)
                elif shape_type in self.multi_handlers:
                    sym.lines.extend(self.multi_handlers[shape_type].parse(parts, context))
            except Exception as exc:
                print(f"  Warning: parse sch {shape_type} failed: {exc}")
                continue
        return sym


__all__ = ["SchematicParser"]
