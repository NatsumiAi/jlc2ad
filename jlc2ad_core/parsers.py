import math
import re
from typing import List, Optional

import requests

from .types import Arc, EASYEDA_PAD_SHAPE, Fill, Footprint, LAYER_MAP, PAD_SHAPE_RECT, Pad, SchArc, SchLine, SchPin, SchRect, SchSymbol, Track, UNIT_SCALE

class EasyEDAClient:
    API_URL = "https://easyeda.com/api/products/{}/components?version=6.4.19.5"

    def fetch(self, lcsc_id: str) -> dict:
        lcsc_id = lcsc_id.strip().upper()
        if not lcsc_id.startswith('C'):
            lcsc_id = 'C' + lcsc_id

        url = self.API_URL.format(lcsc_id)
        resp = requests.get(url, headers={'User-Agent': 'jlc2ad/1.0'}, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if not data.get('success'):
            raise ValueError(f"API error: {data}")

        result = data.get('result')
        if not result:
            raise ValueError(f"Component {lcsc_id} not found")

        pkg = result.get('packageDetail')
        if not pkg:
            raise ValueError(f"Component {lcsc_id} has no footprint data")

        desc = result.get('description', '')
        title = result.get('title', '')
        designator = self._guess_designator(title, desc)
        
        # 从c_para获取更多参数
        sch_data = result.get('dataStr', {})
        c_para = sch_data.get('head', {}).get('c_para', {})
        
        # 获取各个参数
        value = c_para.get('Value', '')
        manufacturer = c_para.get('Manufacturer', '')
        
        return {
            'lcsc_id': lcsc_id,
            'title': title,
            'description': desc if desc else title,
            'value': value,
            'manufacturer': manufacturer,
            'package_name': pkg.get('title', lcsc_id),
            'dataStr': pkg,  # 传入整个packageDetail作为dataStr
            'sch_dataStr': result.get('dataStr', {}),
            'designator': designator,
        }

    @staticmethod
    def _guess_designator(title: str, desc: str) -> str:
        t = (title + ' ' + desc).lower()
        for keys, prefix in [
            (('capacitor', '电容', 'cap'), 'C?'),
            (('resistor', '电阻', 'res'), 'R?'),
            (('inductor', '电感', 'ind'), 'L?'),
            (('diode', '二极管'), 'D?'),
            (('transistor', '三极管', 'mosfet', 'bjt'), 'Q?'),
            (('led',), 'LED?'),
            (('connector', '连接器', 'header'), 'J?'),
            (('crystal', '晶振', 'oscillator'), 'Y?'),
        ]:
            if any(k in t for k in keys):
                return prefix
        return 'U?'


# ============================================================
# EasyEDA PCB 形状解析器
# ============================================================

class FootprintParser:
    def parse(self, component_data: dict) -> Footprint:
        # 使用packageDetail中的dataStr (PCB封装数据)
        pkg_data = component_data.get('dataStr', {})
        ds = pkg_data.get('dataStr', {}) if isinstance(pkg_data, dict) else pkg_data
        origin_x = float(ds.get('head', {}).get('x', 0))
        origin_y = float(ds.get('head', {}).get('y', 0))
        pkg_name = component_data.get('package_name', 'Unknown')
        desc = component_data.get('description', '')

        fp = Footprint(name=pkg_name, description=desc)
        shapes = ds.get('shape', [])

        for shape_str in shapes:
            parts = shape_str.split('~')
            shape_type = parts[0]
            try:
                if shape_type == 'PAD':
                    pad = self._parse_pad(parts, origin_x, origin_y)
                    if pad:
                        fp.pads.append(pad)
                elif shape_type == 'TRACK':
                    tracks = self._parse_track(parts, origin_x, origin_y)
                    fp.tracks.extend(tracks)
                elif shape_type == 'ARC':
                    arc = self._parse_arc(parts, origin_x, origin_y)
                    if arc:
                        fp.arcs.append(arc)
                elif shape_type == 'CIRCLE':
                    arc = self._parse_circle(parts, origin_x, origin_y)
                    if arc:
                        fp.arcs.append(arc)
            except Exception as e:
                print(f"  Warning: parse {shape_type} failed: {e}")
                continue
        return fp

    def _to_altium(self, v: float) -> int:
        return int(round(v * UNIT_SCALE))

    def _rx(self, v: float, o: float) -> int:
        return self._to_altium(v - o)

    def _ry(self, v: float, o: float) -> int:
        return -self._to_altium(v - o)

    def _parse_pad(self, p, ox, oy) -> Optional[Pad]:
        shape_name = p[1]
        cx, cy = float(p[2]), float(p[3])
        w, h = float(p[4]), float(p[5])
        eeda_layer = int(p[6])
        pad_number = p[8] if len(p) > 8 else "1"
        hole_r = float(p[9]) if len(p) > 9 and p[9] else 0
        rot = float(p[11]) if len(p) > 11 and p[11] else 0
        plated = True
        if len(p) > 15 and p[15]:
            plated = p[15].upper() != 'N'

        al = LAYER_MAP.get(eeda_layer, 1)
        ash = EASYEDA_PAD_SHAPE.get(shape_name, PAD_SHAPE_RECT)
        if hole_r > 0 and eeda_layer != 11:
            al = 74

        return Pad(
            x=self._rx(cx, ox), y=self._ry(cy, oy),
            size_x=self._to_altium(w), size_y=self._to_altium(h),
            hole_size=self._to_altium(hole_r * 2),
            shape=ash, rotation=rot, layer=al, name=pad_number, plated=plated,
        )

    def _parse_track(self, p, ox, oy) -> List[Track]:
        width = float(p[1])
        layer = LAYER_MAP.get(int(p[2]) if p[2] else 3, 33)
        coords = (p[4] if len(p) > 4 else "").strip().split(' ')
        tracks = []
        for i in range(0, len(coords) - 2, 2):
            try:
                tracks.append(Track(
                    x1=self._rx(float(coords[i]), ox),
                    y1=self._ry(float(coords[i+1]), oy),
                    x2=self._rx(float(coords[i+2]), ox),
                    y2=self._ry(float(coords[i+3]), oy),
                    width=self._to_altium(width), layer=layer))
            except (ValueError, IndexError):
                continue
        return tracks

    def _parse_arc(self, p, ox, oy) -> Optional[Arc]:
        width = float(p[1])
        layer = LAYER_MAP.get(int(p[2]) if p[2] else 3, 33)
        svg = (p[4] if len(p) > 4 else "").strip()
        m = re.match(
            r'M\s*([\d.\-]+)\s+([\d.\-]+)\s+A\s*([\d.\-]+)\s+([\d.\-]+)\s+'
            r'[\d.\-]+\s+(\d)\s+(\d)\s+([\d.\-]+)\s+([\d.\-]+)', svg)
        if not m:
            return None
        sx, sy = float(m.group(1)), float(m.group(2))
        rx, ry = float(m.group(3)), float(m.group(4))
        la, sw = int(m.group(5)), int(m.group(6))
        ex, ey = float(m.group(7)), float(m.group(8))
        radius = (rx + ry) / 2.0
        cx, cy = self._svg_arc_center(sx, sy, rx, ry, 0, la, sw, ex, ey)
        sa = math.degrees(math.atan2(-(sy - cy), sx - cx)) % 360
        ea = math.degrees(math.atan2(-(ey - cy), ex - cx)) % 360
        if sw == 1:
            sa, ea = ea, sa
        return Arc(center_x=self._rx(cx, ox), center_y=self._ry(cy, oy),
                   radius=self._to_altium(radius),
                   start_angle=sa, end_angle=ea,
                   width=self._to_altium(width), layer=layer)

    def _parse_circle(self, p, ox, oy) -> Optional[Arc]:
        cx, cy = float(p[1]), float(p[2])
        radius = float(p[3])
        width = float(p[4]) if len(p) > 4 and p[4] else 0.15
        layer = LAYER_MAP.get(int(p[5]) if len(p) > 5 and p[5] else 3, 33)
        return Arc(center_x=self._rx(cx, ox), center_y=self._ry(cy, oy),
                   radius=self._to_altium(radius),
                   start_angle=0.0, end_angle=360.0,
                   width=self._to_altium(width), layer=layer)

    @staticmethod
    def _svg_arc_center(x1, y1, rx, ry, phi, fa, fs, x2, y2):
        cos_p, sin_p = math.cos(math.radians(phi)), math.sin(math.radians(phi))
        dx, dy = (x1 - x2) / 2.0, (y1 - y2) / 2.0
        x1p = cos_p * dx + sin_p * dy
        y1p = -sin_p * dx + cos_p * dy
        d = rx*rx*y1p*y1p + ry*ry*x1p*x1p
        if d == 0:
            return (x1+x2)/2, (y1+y2)/2
        sq = max(0, (rx*rx*ry*ry - d) / d) ** 0.5
        if fa == fs:
            sq = -sq
        cxp, cyp = sq*rx*y1p/ry, -sq*ry*x1p/rx
        return (cos_p*cxp - sin_p*cyp + (x1+x2)/2,
                sin_p*cxp + cos_p*cyp + (y1+y2)/2)


# ============================================================
# EasyEDA 原理图符号解析器
# ============================================================

class SchematicParser:
    """解析 EasyEDA 原理图 shape 数据 → SchSymbol"""

    ELEC_MAP = {
        '0': 4,  # unspecified → passive
        '1': 0,  # input
        '2': 2,  # output
        '3': 1,  # bidirectional → IO
        '4': 4,  # passive
    }

    def parse(self, component_data: dict) -> Optional[SchSymbol]:
        ds = component_data.get('sch_dataStr', {})
        if not ds:
            return None
        head = ds.get('head', {})
        origin_x = float(head.get('x', 0))
        origin_y = float(head.get('y', 0))
        
        c_para = head.get('c_para', {})
        
        manufacturer = c_para.get('Manufacturer', '')
        value = c_para.get('Value', '')
        supplier_part = c_para.get('Supplier Part', '')
        
        sym = SchSymbol(
            name=component_data.get('title', 'Unknown'),  # Design Item ID (商品型号)
            designator=component_data.get('designator', 'U?'),
            description=component_data.get('description', ''),
            comment=component_data.get('lcsc_id', ''),  # Comment (商品编号)
            package=c_para.get('package', ''),
            manufacturer=manufacturer,
            value=value,
            supplier_part=supplier_part,
            supplier='LCSC',
        )

        shapes = ds.get('shape', [])
        for shape_str in shapes:
            parts = shape_str.split('~')
            stype = parts[0]
            try:
                if stype == 'P':
                    pin = self._parse_pin(parts, origin_x, origin_y)
                    if pin:
                        sym.pins.append(pin)
                elif stype == 'PL':
                    lines = self._parse_polyline(parts, origin_x, origin_y)
                    sym.lines.extend(lines)
                elif stype == 'PG':
                    lines = self._parse_polygon(parts, origin_x, origin_y)
                    sym.lines.extend(lines)
                elif stype == 'R':
                    rect = self._parse_rect(parts, origin_x, origin_y)
                    if rect:
                        sym.rects.append(rect)
                elif stype == 'E':
                    arc = self._parse_ellipse(parts, origin_x, origin_y)
                    if arc:
                        sym.arcs.append(arc)
                elif stype == 'A':
                    arc = self._parse_arc_path(parts, origin_x, origin_y)
                    if arc:
                        sym.arcs.append(arc)
                elif stype == 'PT':
                    lines = self._parse_svg_path_lines(parts, origin_x, origin_y)
                    sym.lines.extend(lines)
            except Exception as e:
                print(f"  Warning: parse sch {stype} failed: {e}")
                continue
        return sym

    def _rx(self, v: float, o: float) -> int:
        """EasyEDA 原理图坐标 → Altium DXP (10 mil) 单位，直接取整"""
        return int(round(v - o))

    def _ry(self, v: float, o: float) -> int:
        return -int(round(v - o))

    def _parse_pin(self, p, ox, oy) -> Optional[SchPin]:
        if len(p) < 7:
            return None
        electric_str = p[2] if len(p) > 2 else '0'
        header_number = p[3] if len(p) > 3 else ''
        px = float(p[4]) if len(p) > 4 else 0
        py = float(p[5]) if len(p) > 5 else 0
        rot = float(p[6]) if len(p) > 6 else 0

        # EasyEDA pin format uses ^^ to separate sections:
        #   Section 0: P~display~electric~number~x~y~rot~id~locked
        #   Section 1: pinDotX~pinDotY
        #   Section 2: SVG path~color
        #   Section 3: vis~tx~ty~rot~TEXT~POSITION~~~color
        #   Section 4: vis~tx~ty~rot~TEXT~POSITION~~~color
        #   Section 5+: optional clock/dot symbol
        # header_number (p[3]) is always the reliable pin number.
        # From sections 3 and 4, extract any text that differs from the number as pin name.
        full_str = '~'.join(p)
        subsections = full_str.split('^^')

        pin_number = header_number
        pin_name = header_number  # default: same as number
        for sec_idx in (3, 4):
            if len(subsections) > sec_idx:
                fields = subsections[sec_idx].split('~')
                if len(fields) > 4:
                    text = fields[4].strip()
                    if text and text != header_number:
                        pin_name = text
                        break  # found a distinct name

        # Calculate pin length from SVG path
        pin_length = 20  # default 200mil = 20 DXP units
        if len(subsections) >= 3:
            svg_part = subsections[2].strip()
            m = re.match(r'M\s*[\d.\-,]+[\s,][\d.\-]+\s*h\s*([\d.\-]+)', svg_part)
            if m:
                pin_length = abs(int(round(float(m.group(1)))))
            else:
                m = re.match(r'M\s*[\d.\-,]+[\s,][\d.\-]+\s*v\s*([\d.\-]+)', svg_part)
                if m:
                    pin_length = abs(int(round(float(m.group(1)))))

        # EasyEDA rotation → Altium orientation
        orientation = {0: 2, 90: 3, 180: 0, 270: 1}.get(int(rot) % 360, 0)
        electrical = self.ELEC_MAP.get(electric_str, 4)

        return SchPin(
            x=self._rx(px, ox), y=self._ry(py, oy),
            length=max(pin_length, 5),
            orientation=orientation,
            name=pin_name, number=pin_number,
            electrical=electrical,
        )

    def _parse_polyline(self, p, ox, oy) -> List[SchLine]:
        coords_str = p[1] if len(p) > 1 else ""
        width = max(1, int(round(float(p[3])))) if len(p) > 3 and p[3] else 1
        coords = coords_str.strip().split(' ')
        lines = []
        for i in range(0, len(coords) - 2, 2):
            try:
                lines.append(SchLine(
                    x1=self._rx(float(coords[i]), ox),
                    y1=self._ry(float(coords[i+1]), oy),
                    x2=self._rx(float(coords[i+2]), ox),
                    y2=self._ry(float(coords[i+3]), oy),
                    width=width,
                ))
            except (ValueError, IndexError):
                continue
        return lines

    def _parse_polygon(self, p, ox, oy) -> List[SchLine]:
        coords_str = p[1] if len(p) > 1 else ""
        width = max(1, int(round(float(p[3])))) if len(p) > 3 and p[3] else 1
        vals = []
        for t in coords_str.strip().split():
            try:
                vals.append(float(t))
            except ValueError:
                continue
        pts = [(vals[i], vals[i + 1]) for i in range(0, len(vals) - 1, 2)]
        if len(pts) < 2:
            return []

        lines: List[SchLine] = []
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            lines.append(SchLine(
                x1=self._rx(x1, ox),
                y1=self._ry(y1, oy),
                x2=self._rx(x2, ox),
                y2=self._ry(y2, oy),
                width=width,
            ))
        return lines

    def _parse_arc_path(self, p, ox, oy) -> Optional[SchArc]:
        if len(p) < 2:
            return None
        path = p[1].replace(',', ' ')
        m = re.search(
            r'M\s*([\d.\-]+)\s+([\d.\-]+)\s+A\s*([\d.\-]+)\s+([\d.\-]+)\s+[\d.\-]+\s+([01])\s+([01])\s+([\d.\-]+)\s+([\d.\-]+)',
            path,
            flags=re.IGNORECASE,
        )
        if not m:
            return None

        sx, sy = float(m.group(1)), float(m.group(2))
        rx = float(m.group(3))
        ry = float(m.group(4))
        la = int(m.group(5))
        sw = int(m.group(6))
        ex, ey = float(m.group(7)), float(m.group(8))
        width = max(1, int(round(float(p[4])))) if len(p) > 4 and p[4] else 1

        cx, cy = FootprintParser._svg_arc_center(sx, sy, rx, ry, 0, la, sw, ex, ey)
        start_angle = math.degrees(math.atan2(sy - cy, sx - cx))
        end_angle = math.degrees(math.atan2(ey - cy, ex - cx))

        return SchArc(
            cx=self._rx(cx, ox),
            cy=self._ry(cy, oy),
            radius=int(round(rx)),
            start_angle=start_angle,
            end_angle=end_angle,
            width=width,
        )

    def _parse_svg_path_lines(self, p, ox, oy) -> List[SchLine]:
        if len(p) < 2:
            return []
        path = p[1]
        width = max(1, int(round(float(p[3])))) if len(p) > 3 and p[3] else 1

        tokens = re.findall(r'[MLZ]|-?\d+(?:\.\d+)?', path, flags=re.IGNORECASE)
        if not tokens:
            return []

        lines: List[SchLine] = []
        i = 0
        cur = None
        start = None
        cmd = ''

        while i < len(tokens):
            t = tokens[i]
            tu = t.upper()
            if tu in ('M', 'L', 'Z'):
                cmd = tu
                i += 1
                if cmd == 'Z' and cur is not None and start is not None:
                    lines.append(SchLine(
                        x1=self._rx(cur[0], ox),
                        y1=self._ry(cur[1], oy),
                        x2=self._rx(start[0], ox),
                        y2=self._ry(start[1], oy),
                        width=width,
                    ))
                    cur = start
                continue

            if cmd in ('M', 'L') and i + 1 < len(tokens):
                try:
                    x = float(tokens[i])
                    y = float(tokens[i + 1])
                except ValueError:
                    i += 1
                    continue

                if cmd == 'M':
                    cur = (x, y)
                    start = (x, y)
                    cmd = 'L'
                else:
                    if cur is not None:
                        lines.append(SchLine(
                            x1=self._rx(cur[0], ox),
                            y1=self._ry(cur[1], oy),
                            x2=self._rx(x, ox),
                            y2=self._ry(y, oy),
                            width=width,
                        ))
                    cur = (x, y)
                i += 2
            else:
                i += 1

        return lines

    def _parse_rect(self, p, ox, oy) -> Optional[SchRect]:
        # R~x~y~rx~ry~width~height~strokeColor~strokeWidth~fillType~fillStyle~id~locked
        if len(p) < 7:
            return None
        try:
            x, y = float(p[1]), float(p[2])
            w, h = float(p[5]), float(p[6])
            width = max(1, int(round(float(p[8])))) if len(p) > 8 and p[8] else 1
            return SchRect(
                x1=self._rx(x, ox), y1=self._ry(y, oy),
                x2=self._rx(x + w, ox), y2=self._ry(y + h, oy),
                width=width,
            )
        except (ValueError, IndexError):
            return None

    def _parse_ellipse(self, p, ox, oy) -> Optional[SchArc]:
        # E~cx~cy~rx~ry~strokeColor~strokeWidth~fillType~fillColor~id~locked
        if len(p) < 5:
            return None
        cx, cy = float(p[1]), float(p[2])
        rx = float(p[3])
        width = max(1, int(round(float(p[6])))) if len(p) > 6 and p[6] else 1
        return SchArc(
            cx=self._rx(cx, ox), cy=self._ry(cy, oy),
            radius=int(round(rx)),
            start_angle=0.0, end_angle=360.0, width=width,
        )


# ============================================================
# PcbLib 二进制记录打包 (基于 AltiumSharp 格式)
# ============================================================

