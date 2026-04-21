from .footprint_shapes import ArcHandler, CircleHandler, FootprintParseContext, PadHandler, TrackHandler
from .geometry import CoordinateTransformer, svg_arc_center
from .types import Footprint, UNIT_SCALE


class FootprintParser:
    def __init__(self):
        self.coords = CoordinateTransformer(scale=UNIT_SCALE, invert_y=True)
        self.single_handlers = {
            'PAD': PadHandler(),
            'ARC': ArcHandler(),
            'CIRCLE': CircleHandler(),
        }
        self.multi_handlers = {
            'TRACK': TrackHandler(),
        }

    def parse(self, component_data: dict) -> Footprint:
        pkg_data = component_data.get('dataStr', {})
        ds = pkg_data.get('dataStr', {}) if isinstance(pkg_data, dict) else pkg_data
        origin_x = float(ds.get('head', {}).get('x', 0))
        origin_y = float(ds.get('head', {}).get('y', 0))
        pkg_name = component_data.get('package_name', 'Unknown')
        desc = component_data.get('description', '')

        fp = Footprint(name=pkg_name, description=desc)
        shapes = ds.get('shape', [])
        context = FootprintParseContext(origin_x=origin_x, origin_y=origin_y, coords=self.coords)

        for shape_str in shapes:
            parts = shape_str.split('~')
            shape_type = parts[0]
            try:
                if shape_type in self.single_handlers:
                    shape = self.single_handlers[shape_type].parse(parts, context)
                    if shape_type == 'PAD' and shape:
                        fp.pads.append(shape)
                    elif shape:
                        fp.arcs.append(shape)
                elif shape_type in self.multi_handlers:
                    fp.tracks.extend(self.multi_handlers[shape_type].parse(parts, context))
            except Exception as exc:
                print(f"  Warning: parse {shape_type} failed: {exc}")
                continue
        return fp

    _svg_arc_center = staticmethod(svg_arc_center)


__all__ = ["FootprintParser"]
