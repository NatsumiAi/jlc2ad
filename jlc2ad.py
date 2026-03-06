#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
jlc2ad.py - 从立创商城(LCSC)获取元件封装和原理图符号，转换为 Altium Designer 格式
生成 PcbLib (PCB封装库) + SchLib (原理图库) + LibPkg (集成库项目文件)

用法:
    python jlc2ad.py C15850 -o my_lib
    python jlc2ad.py C15850 C25804 C7171 -o my_lib
    python jlc2ad.py C100023 -o my_lib   # 已有文件则追加

依赖: pip install requests olefile

格式参考: https://github.com/issus/AltiumSharp (MIT License)
"""

import struct
import math
import re
import sys
import os
import argparse
import zlib
import base64
from dataclasses import dataclass, field
from typing import List, Optional

import requests

# ============================================================
# 常量
# ============================================================

LAYER_MAP = {
    1:  1,    # TopLayer
    2:  32,   # BottomLayer
    3:  33,   # TopSilkLayer -> TopOverlay
    4:  34,   # BottomSilkLayer -> BottomOverlay
    5:  35,   # TopPasteMaskLayer -> TopPaste
    6:  36,   # BottomPasteMaskLayer -> BottomPaste
    7:  37,   # TopSolderMaskLayer -> TopSolder
    8:  38,   # BottomSolderMaskLayer -> BottomSolder
    9:  45,   # Ratlines -> Signal (not used)
    10: 20,   # BoardOutLine -> Mechanical15
    11: 74,   # Multi-Layer
    12: 8,    # Document -> Comment
    13: 13,   # TopAssembly -> Mechanical4
    14: 14,   # BottomAssembly -> Mechanical5
    15: 1,    # Mechanical -> Mechanical1
    19: 55,   # 3DModel -> 3D Model
    # Inner layers (21-52) -> Internal Signal (1-16)
    21: 41,   # Inner1
    22: 42,   # Inner2
    23: 43,   # Inner3
    24: 44,   # Inner4
    25: 45,   # Inner5
    26: 46,   # Inner6
    27: 47,   # Inner7
    28: 48,   # Inner8
    29: 49,   # Inner9
    30: 50,   # Inner10
    31: 51,   # Inner11
    32: 52,   # Inner12
    33: 53,   # Inner13
    34: 54,   # Inner14
    35: 55,   # Inner15
    36: 56,   # Inner16
    99: 57,   # ComponentShapeLayer -> Mechanical1
    100: 57,  # LeadShapeLayer -> Mechanical1
    101: 57,  # ComponentPolarityLayer -> Mechanical1
    # Hole -> MultiLayer
}

PAD_SHAPE_ROUND = 1
PAD_SHAPE_RECT = 2
PAD_SHAPE_OCTAGONAL = 3
PAD_SHAPE_OVAL = 9

EASYEDA_PAD_SHAPE = {
    'ELLIPSE': PAD_SHAPE_ROUND,
    'RECT': PAD_SHAPE_RECT,
    'OVAL': PAD_SHAPE_OVAL,
    'POLYGON': PAD_SHAPE_RECT,
}

# 1 EasyEDA PCB unit = 10 mil, 1 Altium internal unit = 1/10000 mil
UNIT_SCALE = 100000

# PCB 图元标志位: 0x04 = Unlocked (参考 AltiumSharp PcbBinaryConstants)
PCB_FLAGS_UNLOCKED = 0x0004


# ============================================================
# 数据类 - PCB
# ============================================================

@dataclass
class Pad:
    x: int = 0
    y: int = 0
    size_x: int = 0
    size_y: int = 0
    hole_size: int = 0
    shape: int = PAD_SHAPE_RECT
    rotation: float = 0.0
    layer: int = 1
    name: str = "1"
    plated: bool = True

@dataclass
class Track:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    width: int = 0
    layer: int = 33

@dataclass
class Arc:
    center_x: int = 0
    center_y: int = 0
    radius: int = 0
    start_angle: float = 0.0
    end_angle: float = 0.0
    width: int = 0
    layer: int = 33

@dataclass
class Fill:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    rotation: float = 0.0
    layer: int = 1

@dataclass
class Footprint:
    name: str = ""
    description: str = ""
    height: str = "0mil"
    pads: List[Pad] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    arcs: List[Arc] = field(default_factory=list)
    fills: List[Fill] = field(default_factory=list)


# ============================================================
# 数据类 - 原理图
# ============================================================

@dataclass
class SchPin:
    x: int = 0          # DXP units (10 mil)
    y: int = 0
    length: int = 20     # DXP units
    orientation: int = 0 # 0=right, 1=up, 2=left, 3=down
    name: str = ""
    number: str = ""
    electrical: int = 4  # 0=input, 1=IO, 2=output, 3=OC, 4=passive

@dataclass
class SchLine:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    width: int = 1

@dataclass
class SchRect:
    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0
    width: int = 1
    fill_color: int = 16777215  # white

@dataclass
class SchArc:
    cx: int = 0
    cy: int = 0
    radius: int = 0
    start_angle: float = 0.0
    end_angle: float = 360.0
    width: int = 1

@dataclass
class SchSymbol:
    name: str = ""  # Design Item ID (商品型号)
    designator: str = "U?"
    description: str = ""
    comment: str = ""  # 商品编号 (LCSC ID)
    package: str = ""  # 封装
    manufacturer: str = ""  # 厂商
    value: str = ""  # 值
    supplier_part: str = ""  # 供应商型号
    supplier: str = "LCSC"  # 供应商
    pins: List[SchPin] = field(default_factory=list)
    lines: List[SchLine] = field(default_factory=list)
    rects: List[SchRect] = field(default_factory=list)
    arcs: List[SchArc] = field(default_factory=list)


# ============================================================
# EasyEDA API 客户端
# ============================================================

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
                elif stype == 'R':
                    rect = self._parse_rect(parts, origin_x, origin_y)
                    if rect:
                        sym.rects.append(rect)
                elif stype == 'E':
                    arc = self._parse_ellipse(parts, origin_x, origin_y)
                    if arc:
                        sym.arcs.append(arc)
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

class RecordPacker:

    def _common_header(self, layer: int) -> bytearray:
        """图元通用头 (13 bytes): [u8 layer][u16 flags][10×0xFF]"""
        h = bytearray(13)
        h[0] = layer & 0xFF
        struct.pack_into('<H', h, 1, PCB_FLAGS_UNLOCKED)
        h[3:13] = b'\xFF' * 10
        return h

    def pack_pad(self, pad: Pad) -> bytes:
        """Pad = type(0x02) + 6 sub-blocks (AltiumSharp format)"""
        rec = bytearray([0x02])

        # Block 1: StringBlock(designator) = [u32 (1+n)][u8 n][ascii]
        des = pad.name.encode('ascii', errors='replace')
        rec.extend(struct.pack('<I', 1 + len(des)))
        rec.append(len(des))
        rec.extend(des)

        # Block 2: reserved [u32 1][0x00]
        rec.extend(struct.pack('<I', 1))
        rec.append(0)

        # Block 3: StringBlock("|&|0") = [u32 5][u8 4]["|&|0"]
        net_str = b"|&|0"
        rec.extend(struct.pack('<I', 1 + len(net_str)))
        rec.append(len(net_str))
        rec.extend(net_str)

        # Block 4: reserved [u32 1][0x00]
        rec.extend(struct.pack('<I', 1))
        rec.append(0)

        # Block 5: main pad data (114 bytes)
        pd = bytearray(114)
        hdr = self._common_header(pad.layer)
        pd[:13] = hdr
        struct.pack_into('<i', pd, 13, pad.x)
        struct.pack_into('<i', pd, 17, pad.y)
        struct.pack_into('<i', pd, 21, pad.size_x)    # SizeTop.X
        struct.pack_into('<i', pd, 25, pad.size_y)    # SizeTop.Y
        struct.pack_into('<i', pd, 29, pad.size_x)    # SizeMid.X
        struct.pack_into('<i', pd, 33, pad.size_y)    # SizeMid.Y
        struct.pack_into('<i', pd, 37, pad.size_x)    # SizeBot.X
        struct.pack_into('<i', pd, 41, pad.size_y)    # SizeBot.Y
        struct.pack_into('<i', pd, 45, pad.hole_size)  # HoleSize
        pd[49] = pad.shape   # ShapeTop
        pd[50] = pad.shape   # ShapeMid
        pd[51] = pad.shape   # ShapeBot
        struct.pack_into('<d', pd, 52, pad.rotation)
        pd[60] = 1 if pad.plated else 0  # IsPlated
        # offset 61: constant 0
        # offset 62: StackMode = 0 (Simple)
        # offset 63: PowerPlaneConnectStyle = 0
        # offset 64-67: ReliefAirGap = 0 (use rule)
        # offset 68-71: ReliefConductorWidth = 0 (use rule)
        struct.pack_into('<h', pd, 72, 4)  # ReliefEntries = 4 (default)
        # offset 74-113: remaining fields default to 0
        rec.extend(struct.pack('<I', len(pd)))
        rec.extend(pd)

        # Block 6: size/shape block (empty for simple pads)
        rec.extend(struct.pack('<I', 0))

        return bytes(rec)

    def pack_track(self, track: Track) -> bytes:
        """Track = type(0x04) + 1 block (36 bytes)"""
        sr = bytearray(36)
        sr[:13] = self._common_header(track.layer)
        struct.pack_into('<i', sr, 13, track.x1)
        struct.pack_into('<i', sr, 17, track.y1)
        struct.pack_into('<i', sr, 21, track.x2)
        struct.pack_into('<i', sr, 25, track.y2)
        struct.pack_into('<i', sr, 29, track.width)
        struct.pack_into('<H', sr, 33, 0)  # NetIndex: ushort (2 bytes)
        sr[35] = 0  # ComponentIndex: byte (1 byte)
        rec = bytearray([0x04])
        rec.extend(struct.pack('<I', len(sr)))
        rec.extend(sr)
        return bytes(rec)

    def pack_arc(self, arc: Arc) -> bytes:
        """Arc = type(0x01) + 1 block (45 bytes)"""
        sr = bytearray(45)
        sr[:13] = self._common_header(arc.layer)
        struct.pack_into('<i', sr, 13, arc.center_x)
        struct.pack_into('<i', sr, 17, arc.center_y)
        struct.pack_into('<i', sr, 21, arc.radius)
        struct.pack_into('<d', sr, 25, arc.start_angle)
        struct.pack_into('<d', sr, 33, arc.end_angle)
        struct.pack_into('<i', sr, 41, arc.width)
        rec = bytearray([0x01])
        rec.extend(struct.pack('<I', len(sr)))
        rec.extend(sr)
        return bytes(rec)

    def pack_fill(self, fill: Fill) -> bytes:
        """Fill = type(0x06) + 1 block (37 bytes)"""
        sr = bytearray(37)
        sr[:13] = self._common_header(fill.layer)
        struct.pack_into('<i', sr, 13, fill.x1)
        struct.pack_into('<i', sr, 17, fill.y1)
        struct.pack_into('<i', sr, 21, fill.x2)
        struct.pack_into('<i', sr, 25, fill.y2)
        struct.pack_into('<d', sr, 29, fill.rotation)
        rec = bytearray([0x06])
        rec.extend(struct.pack('<I', len(sr)))
        rec.extend(sr)
        return bytes(rec)


# ============================================================
# OLE / CFB 复合文件写入器
# ============================================================

class CfbWriter:
    """OLE/CFB 文件写入器 - 使用 Windows 原生 OLE32 API (通过 ctypes)"""

    # STGM flags
    STGM_DIRECT = 0x00000000
    STGM_READWRITE = 0x00000002
    STGM_SHARE_EXCLUSIVE = 0x00000010
    STGM_CREATE = 0x00001000
    STGM_WRITE = 0x00000001

    def __init__(self):
        self._streams = {}  # path -> data

    def add_stream(self, path: str, data: bytes):
        self._streams[path.replace('\\', '/')] = data

    def save(self, filename: str):
        import ctypes
        from ctypes import c_void_p, POINTER, byref, c_ulong

        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        # Create root IStorage
        root_stg = c_void_p()
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE | self.STGM_DIRECT
        hr = ole32.StgCreateDocfile(
            ctypes.c_wchar_p(os.path.abspath(filename)),
            c_ulong(mode), c_ulong(0), byref(root_stg))
        if hr != 0:
            raise OSError(f"StgCreateDocfile failed: 0x{hr & 0xFFFFFFFF:08X}")

        try:
            storage_cache = {'': root_stg}
            for path, data in self._streams.items():
                parts = path.split('/')
                # Ensure parent storages exist
                for i in range(len(parts) - 1):
                    spath = '/'.join(parts[:i + 1])
                    if spath not in storage_cache:
                        parent_path = '/'.join(parts[:i]) if i > 0 else ''
                        parent_stg = storage_cache[parent_path]
                        child_stg = c_void_p()
                        hr = self._create_storage(parent_stg, parts[i], child_stg)
                        if hr != 0:
                            raise OSError(f"CreateStorage '{parts[i]}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                        storage_cache[spath] = child_stg

                # Create stream and write data
                parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''
                parent_stg = storage_cache[parent_path]
                stream_name = parts[-1]
                stm = c_void_p()
                hr = self._create_stream(parent_stg, stream_name, stm)
                if hr != 0:
                    raise OSError(f"CreateStream '{stream_name}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                if data:
                    written = c_ulong(0)
                    buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
                    hr = self._stream_write(stm, buf, len(data), written)
                    if hr != 0:
                        raise OSError(f"Write to '{path}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                self._release(stm)

            # Commit all storages (children first), then release
            for spath in reversed(list(storage_cache.keys())):
                stg = storage_cache[spath]
                self._commit(stg)
            for spath in reversed(list(storage_cache.keys())):
                if spath:  # don't release root yet
                    self._release(storage_cache[spath])
        finally:
            self._release(root_stg)
            ole32.CoUninitialize()

    @staticmethod
    def _get_vtable(obj):
        """Get COM vtable from object pointer"""
        import ctypes
        return ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

    def _create_storage(self, parent_stg, name, out_stg):
        """IStorage::CreateStorage (vtable index 5)"""
        import ctypes
        from ctypes import c_void_p, c_ulong, byref
        vt = self._get_vtable(parent_stg)
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_wchar_p, c_ulong, c_ulong, c_ulong, ctypes.POINTER(c_void_p))
        func = func_type(vt[5])
        return func(parent_stg, name, mode, 0, 0, byref(out_stg))

    def _create_stream(self, parent_stg, name, out_stm):
        """IStorage::CreateStream (vtable index 3)"""
        import ctypes
        from ctypes import c_void_p, c_ulong, byref
        vt = self._get_vtable(parent_stg)
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_wchar_p, c_ulong, c_ulong, c_ulong, ctypes.POINTER(c_void_p))
        func = func_type(vt[3])
        return func(parent_stg, name, mode, 0, 0, byref(out_stm))

    def _commit(self, stg):
        """IStorage::Commit (vtable index 9) - STGC_DEFAULT=0"""
        import ctypes
        from ctypes import c_void_p, c_ulong
        vt = self._get_vtable(stg)
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, c_ulong)
        func = func_type(vt[9])
        return func(stg, 0)

    def _stream_write(self, stm, buf, cb, written):
        """IStream::Write (vtable index 4)"""
        import ctypes
        from ctypes import c_void_p, c_ulong, byref
        vt = self._get_vtable(stm)
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_void_p, c_ulong, ctypes.POINTER(c_ulong))
        func = func_type(vt[4])
        return func(stm, buf, cb, byref(written))

    @staticmethod
    def _release(obj):
        """IUnknown::Release (vtable index 2)"""
        import ctypes
        from ctypes import c_void_p
        if obj and obj.value:
            vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
            func_type = ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)
            func = func_type(vt[2])
            func(obj)


# ============================================================
# 二进制格式辅助函数 (对应 AltiumSharp BinaryFormatWriter)
# ============================================================

def _write_string_block(name: str) -> bytes:
    """WriteStringBlock: [u32 (1+n)][u8 n][ascii_string]"""
    b = name.encode('ascii', errors='replace')
    buf = struct.pack('<I', 1 + len(b))
    buf += struct.pack('B', len(b))
    buf += b
    return buf


def _write_cstring_param_block(params: dict) -> bytes:
    """WriteCStringParameterBlock: [u32 len]["|K=V|K=V\0"]"""
    text = ''.join(f"|{k}={v}" for k, v in params.items())
    try:
        data = text.encode('gbk') + b'\x00'
    except UnicodeEncodeError:
        data = text.encode('utf-8', errors='replace') + b'\x00'
    return struct.pack('<I', len(data)) + data


# ============================================================
# PcbLib 文件写入器 (基于 AltiumSharp 格式)
# ============================================================

def _load_file_header() -> bytes:
    """Load FileHeader template from RC.PcbLib."""
    header_file = os.path.join(os.path.dirname(__file__), 'pcb_file_header.bin')
    if os.path.exists(header_file):
        with open(header_file, 'rb') as f:
            return f.read()
    return None


PCB_FILE_HEADER_TEMPLATE = None


def _get_file_header() -> bytes:
    """Get FileHeader, loading from file if needed."""
    global PCB_FILE_HEADER_TEMPLATE
    if PCB_FILE_HEADER_TEMPLATE is None:
        PCB_FILE_HEADER_TEMPLATE = _load_file_header()
    return PCB_FILE_HEADER_TEMPLATE


def _load_library_params() -> str:
    """Load full PCB library params template from file."""
    params_file = os.path.join(os.path.dirname(__file__), 'pcb_library_params.txt')
    if os.path.exists(params_file):
        with open(params_file, 'r', encoding='utf-8') as f:
            return f.read()
    return None


PCB_LIBRARY_PARAMS_TEMPLATE = None


def _get_library_params() -> str:
    """Get full library params, loading from file if needed."""
    global PCB_LIBRARY_PARAMS_TEMPLATE
    if PCB_LIBRARY_PARAMS_TEMPLATE is None:
        PCB_LIBRARY_PARAMS_TEMPLATE = _load_library_params()
    return PCB_LIBRARY_PARAMS_TEMPLATE


class PcbLibWriter:
    def __init__(self):
        self.packer = RecordPacker()

    @staticmethod
    def _make_file_header() -> bytes:
        """AltiumSharp: WriteFileHeader - use template from RC"""
        template = _get_file_header()
        if template:
            return template
        # Fallback
        buf = bytearray()
        s = b"PCB 6.0 Binary Library File"
        buf.extend(struct.pack('<i', len(s)))
        buf.append(len(s))
        buf.extend(s)
        buf.extend(struct.pack('<d', 5.01))
        buf.extend(struct.pack('<h', 8))
        buf.append(0)
        uid = b"JLC2ADPY"
        buf.append(len(uid))
        buf.extend(uid)
        return bytes(buf)

    def _make_library_data(self, storage_names: List[str], filename: str) -> bytes:
        """AltiumSharp: WriteLibraryData - board props + SectionKeys"""
        buf = bytearray()
        
        # Part 1: WriteCStringParameterBlock - use full params from RC
        full_params = _get_library_params()
        if full_params:
            # Replace FILENAME with actual output file path
            # Replace WEIGHT with actual component count
            full_params = full_params.replace(
                'FILENAME=D:\\BrainCoWorkspace\\AltiumDesignerLibPkg-dream\\RC\\RC.$$$',
                f'FILENAME={filename}$$$'
            )
            # Find and replace WEIGHT
            import re
            full_params = re.sub(r'\|WEIGHT=\d+', f'|WEIGHT={len(storage_names)}', full_params)
            params_bytes = full_params.encode('ascii', errors='replace') + b'\x00'
            buf.extend(struct.pack('<I', len(params_bytes)))
            buf.extend(params_bytes)
        else:
            # Fallback to minimal params if template file not found
            params = {
                'HEADER': 'PCB 6.0 Binary Library File',
                'WEIGHT': str(len(storage_names)),
            }
            buf.extend(_write_cstring_param_block(params))
        
        # Part 2: component count + names
        buf.extend(struct.pack('<I', len(storage_names)))
        for sn in storage_names:
            buf.extend(_write_string_block(sn))
        return bytes(buf)

    def _build_component_data(self, fp: Footprint, storage_name: str) -> bytes:
        """AltiumSharp: WriteFootprintData"""
        buf = bytearray()
        # First record: WriteStringBlock(component name)
        buf.extend(_write_string_block(storage_name))
        # Primitive records
        for pad in fp.pads:
            buf.extend(self.packer.pack_pad(pad))
        for track in fp.tracks:
            buf.extend(self.packer.pack_track(track))
        for arc in fp.arcs:
            buf.extend(self.packer.pack_arc(arc))
        for fill in fp.fills:
            buf.extend(self.packer.pack_fill(fill))
        return bytes(buf)

    @staticmethod
    def _build_header(fp: Footprint) -> bytes:
        return struct.pack('<I',
            len(fp.pads) + len(fp.tracks) + len(fp.arcs) + len(fp.fills))

    @staticmethod
    def _build_parameters(fp: Footprint, storage_name: str) -> bytes:
        """AltiumSharp: WriteFootprintParameters"""
        params = {
            'PATTERN': fp.name,
            'HEIGHT': '0',
        }
        # 添加各个参数字段
        if getattr(fp, 'value', ''):
            params['Value'] = fp.value
        if getattr(fp, 'manufacturer', ''):
            params['Manufacturer'] = fp.manufacturer
        if getattr(fp, 'description', ''):
            params['DESCRIPTION'] = fp.description
        return _write_cstring_param_block(params)

    @staticmethod
    def _build_wide_strings() -> bytes:
        """AltiumSharp: WriteWideStrings - empty params block"""
        return _write_cstring_param_block({})

    def _build_cfb(self, footprints: List[Footprint],
                    storage_names: List[str],
                    filename: str = '',
                    existing_raw: dict = None) -> CfbWriter:
        """Build OLE compound file - minimal AltiumSharp format."""
        cfb = CfbWriter()
        cfb.add_stream('FileHeader', self._make_file_header())

        all_sn = list((existing_raw or {}).keys()) + storage_names

        # Library storage (matches AltiumSharp WriteLibrary)
        cfb.add_stream('Library/Header', struct.pack('<I', 1))
        cfb.add_stream('Library/Data', self._make_library_data(all_sn, filename))
        # Library/Models (required even with 0 models)
        cfb.add_stream('Library/Models/Header', struct.pack('<I', 0))
        cfb.add_stream('Library/Models/Data', b'')

        # Write back existing components
        if existing_raw:
            for sn, streams in existing_raw.items():
                for stream_name, data in streams.items():
                    cfb.add_stream(f'{sn}/{stream_name}', data)

        # Write new footprints (matches AltiumSharp WriteFootprint)
        for fp, sn in zip(footprints, storage_names):
            cfb.add_stream(f'{sn}/Header', self._build_header(fp))
            cfb.add_stream(f'{sn}/Parameters', self._build_parameters(fp, sn))
            cfb.add_stream(f'{sn}/WideStrings', self._build_wide_strings())
            cfb.add_stream(f'{sn}/Data', self._build_component_data(fp, sn))

        return cfb

    @staticmethod
    def _safe_name(name: str) -> str:
        s = name.replace('/', '_').replace('\\', '_')
        return s[:31]

    def write(self, filename: str, footprints: List[Footprint]):
        storage_names = [self._safe_name(fp.name) for fp in footprints]
        cfb = self._build_cfb(footprints, storage_names, filename)
        cfb.save(filename)

    def append(self, filename: str, footprints: List[Footprint]):
        import olefile

        existing_raw = {}
        existing_names = set()

        if os.path.exists(filename):
            ole = olefile.OleFileIO(filename)
            for entry in ole.listdir(storages=True):
                if (len(entry) == 1
                        and entry[0] not in ('FileHeader', 'Library',
                                              'FileVersionInfo', 'SectionKeys')):
                    cn = entry[0]
                    if cn not in existing_names:
                        existing_names.add(cn)
            for name in existing_names:
                existing_raw[name] = {}
                for sn in ('Data', 'Header', 'Parameters', 'WideStrings'):
                    try:
                        existing_raw[name][sn] = ole.openstream(
                            f'{name}/{sn}').read()
                    except Exception:
                        pass
            ole.close()

        new_fps, new_sns = [], []
        for fp in footprints:
            sn = self._safe_name(fp.name)
            if sn in existing_names:
                print(f"  Skipping existing: {sn}")
                continue
            new_fps.append(fp)
            new_sns.append(sn)

        cfb = self._build_cfb(new_fps, new_sns, filename, existing_raw)
        cfb.save(filename)


# ============================================================
# SchLib 模板加载
# ============================================================

def _load_sch_file_header() -> bytes:
    """Load SchLib FileHeader template from RC.SchLib."""
    header_file = os.path.join(os.path.dirname(__file__), 'sch_file_header.bin')
    if os.path.exists(header_file):
        with open(header_file, 'rb') as f:
            return f.read()
    return None


def _load_sch_storage() -> bytes:
    """Load SchLib Storage template from RC.SchLib."""
    storage_file = os.path.join(os.path.dirname(__file__), 'sch_storage.bin')
    if os.path.exists(storage_file):
        with open(storage_file, 'rb') as f:
            return f.read()
    return None


SCH_FILE_HEADER_TEMPLATE = None
SCH_STORAGE_TEMPLATE = None


def _get_sch_file_header() -> bytes:
    """Get SchLib FileHeader, loading from file if needed."""
    global SCH_FILE_HEADER_TEMPLATE
    if SCH_FILE_HEADER_TEMPLATE is None:
        SCH_FILE_HEADER_TEMPLATE = _load_sch_file_header()
    return SCH_FILE_HEADER_TEMPLATE


def _get_sch_storage() -> bytes:
    """Get SchLib Storage, loading from file if needed."""
    global SCH_STORAGE_TEMPLATE
    if SCH_STORAGE_TEMPLATE is None:
        SCH_STORAGE_TEMPLATE = _load_sch_storage()
    return SCH_STORAGE_TEMPLATE


# ============================================================
# SchLib 文件写入器 (基于 AltiumSharp 格式)
# ============================================================

class SchLibWriter:
    """生成 Altium Designer SchLib 格式文件"""

    def _make_file_header(self, storage_names: List[str]) -> bytes:
        """AltiumSharp: WriteFileHeader - use template but fix weight"""
        template = _get_sch_file_header()
        if template:
            import re
            template = re.sub(rb'\|Weight=\d+', f'|Weight={len(storage_names)}'.encode(), template)
            return template
        # Fallback
        buf = bytearray()
        params = {
            'HEADER': 'Protel for Windows - Schematic Library Editor Binary File Version 5.0',
            'Weight': str(len(storage_names)),
        }
        buf.extend(_write_cstring_param_block(params))
        buf.extend(struct.pack('<i', len(storage_names)))
        for sn in storage_names:
            buf.extend(_write_string_block(sn))
        return bytes(buf)

    def _write_text_record(self, params: dict) -> bytes:
        """Write a text property record: [u32 len]["|K=V\0"]"""
        return _write_cstring_param_block(params)

    def _write_pin_binary(self, pin: SchPin) -> bytes:
        """Write a binary pin record: [u32 (0x01000000|len)][binary_data]
        AltiumSharp: WritePinRecord with flag=0x01
        """
        data = bytearray()
        data.extend(struct.pack('<i', 2))  # Record type = Pin (int32)
        data.append(0)                      # Unknown
        data.extend(struct.pack('<h', 1))   # OwnerPartId = 1
        data.append(0)                      # OwnerPartDisplayMode
        data.append(0)                      # SymbolInnerEdge
        data.append(0)                      # SymbolOuterEdge
        data.append(0)                      # SymbolInside
        data.append(0)                      # SymbolOutside
        # Description (PascalShortString)
        data.append(0)  # empty description
        data.append(0)  # FormalType
        data.append(pin.electrical & 0xFF)
        # PINCONGLOMERATE: orientation in bits 0-1, bit 3=show name, bit 4=show designator
        # Show name (bit 3 = 0x08), hide designator (bit 4 cleared), always set (bit 5 = 0x20)
        conglomerate = (pin.orientation & 0x03) | 0x08 | 0x20
        data.append(conglomerate)
        data.extend(struct.pack('<h', pin.length))    # PinLength (int16, DXP)
        data.extend(struct.pack('<h', pin.x))         # Location.X (int16, DXP)
        data.extend(struct.pack('<h', pin.y))         # Location.Y (int16, DXP)
        data.extend(struct.pack('<i', 128))           # Color (dark green = 128)
        # PascalShortStrings: Name, Designator, SwapIdGroup, PartAndSequence, DefaultValue
        name_b = pin.name.encode('ascii', errors='replace')
        data.append(len(name_b))
        data.extend(name_b)
        des_b = pin.number.encode('ascii', errors='replace')
        data.append(len(des_b))
        data.extend(des_b)
        data.append(0)  # SwapIdGroup = empty
        swap = b"|&|"
        data.append(len(swap))
        data.extend(swap)
        data.append(0)  # DefaultValue = empty

        # Pack with flag byte 0x01 in upper byte of length
        length = len(data)
        size_word = (0x01 << 24) | length
        return struct.pack('<I', size_word) + bytes(data)

    def _build_component_data(self, sym: SchSymbol, storage_name: str) -> bytes:
        """构建组件 Data 流 (record order matches AltiumSharp)"""
        buf = bytearray()

        # ComponentDescription只填原始description
        component_desc = sym.description if sym.description else sym.name

        # 构建Model关联字段 (嵌入到ComponentDescription)
        model_field = ''
        if sym.package:
            import uuid
            model_uid = uuid.uuid4().hex[:12].upper()
            model_field = (
                f"|Model=T|DatabaseModel=T|UniqueID={model_uid}"
            )

        # RECORD=1: Component definition
        buf.extend(self._write_text_record({
            'RECORD': '1',
            'LibReference': storage_name,
            'ComponentDescription': component_desc + model_field,
            'PartCount': '2',
            'DisplayModeCount': '1',
            'IndexInSheet': '-1',
            'OwnerPartId': '-1',
            'CurrentPartId': '1',
            'LibraryPath': '*',
            'SourceLibraryName': '*',
            'SheetPartFileName': '*',
            'TargetFileName': '*',
            'AreaColor': '11599871',
            'Color': '128',
        }))

        # RECORD=2: Pins
        for pin in sym.pins:
            buf.extend(self._write_pin_binary(pin))

        # RECORD=45-48: Model records (PCB封装关联)
        if sym.package:
            # Use same UID as in component description (already generated above)
            # RECORD=45 (Model data) - 放在最前面
            buf.extend(self._write_text_record({
                'RECORD': '45',
                'OwnerIndex': '7',
                'IndexInSheet': '-1',
                'Description': sym.package,
                'ModelName': sym.package,
                'ModelType': 'PCBLib',
                'DatafileCount': '1',
                'ModelDatafileEntity0': sym.package,
                'ModelDatafileKind0': 'PCBLib',
                'IsCurrent': 'T',
                'IntegratedModel': 'T',
                'ModelHandle': '1',
            }))
            
            # RECORD=46
            buf.extend(self._write_text_record({
                'RECORD': '46',
                'OwnerIndex': '8',
            }))
            
            # RECORD=48
            buf.extend(self._write_text_record({
                'RECORD': '48',
                'OwnerIndex': '8',
            }))

        # RECORD=13: Lines (text records)
        for line in sym.lines:
            buf.extend(self._write_text_record({
                'RECORD': '13',
                'OwnerIndex': '0',
                'IsNotAccesible': 'T',
                'IndexInSheet': '-1',
                'OwnerPartId': '1',
                'Location.X': str(line.x1),
                'Location.Y': str(line.y1),
                'Corner.X': str(line.x2),
                'Corner.Y': str(line.y2),
                'LineWidth': '1',
                'LineStyle': '0',
                'Color': '128',
            }))

        # RECORD=14: Rectangles (text records)
        for rect in sym.rects:
            buf.extend(self._write_text_record({
                'RECORD': '14',
                'OwnerIndex': '0',
                'IsNotAccesible': 'T',
                'IndexInSheet': '-1',
                'OwnerPartId': '1',
                'Location.X': str(rect.x1),
                'Location.Y': str(rect.y1),
                'Corner.X': str(rect.x2),
                'Corner.Y': str(rect.y2),
                'LineWidth': '1',
                'LineStyle': '0',
                'Color': '128',
                'AreaColor': '11599871',
                'IsSolid': 'T',
                'Transparent': 'T',
            }))

        # RECORD=12: Arcs (text records)
        for arc in sym.arcs:
            params = {
                'RECORD': '12',
                'OwnerIndex': '0',
                'IsNotAccesible': 'T',
                'IndexInSheet': '-1',
                'OwnerPartId': '1',
                'Location.X': str(arc.cx),
                'Location.Y': str(arc.cy),
                'Radius': str(arc.radius),
                'LineWidth': '1',
                'LineStyle': '0',
                'EndAngle': f'{arc.end_angle:.3f}',
                'Color': '128',
            }
            if arc.start_angle != 0:
                params['StartAngle'] = f'{arc.start_angle:.3f}'
            buf.extend(self._write_text_record(params))

        # RECORD=34: Designator parameter — after graphics primitives
        buf.extend(self._write_text_record({
            'RECORD': '34',
            'OwnerIndex': '0',
            'IndexInSheet': '-1',
            'OwnerPartId': '-1',
            'Location.X': '1',
            'Location.Y': '1',
            'Color': '8388608',
            'FontID': '1',
            'Text': sym.designator,
            'Name': 'Designator',
            'ReadOnlyState': '1',
            'IsHidden': 'T',
        }))

        # RECORD=41: Comment parameter - 商品编号 (LCSC ID)
        buf.extend(self._write_text_record({
            'RECORD': '41',
            'OwnerIndex': '0',
            'IndexInSheet': '-1',
            'OwnerPartId': '-1',
            'Location.X': '1',
            'Location.Y': '-1',
            'Color': '8388608',
            'FontID': '1',
            'Text': sym.comment if sym.comment else sym.name,
            'Name': 'Comment',
            'ReadOnlyState': '1',
            'IsHidden': 'T',
        }))

        # RECORD=41: Symbol - 商品型号
        buf.extend(self._write_text_record({
            'RECORD': '41',
            'OwnerIndex': '0',
            'IndexInSheet': '1',
            'OwnerPartId': '-1',
            'FontID': '2',
            'IsHidden': 'T',
            'Text': sym.name,
            'Name': 'Symbol',
        }))

        # RECORD=41: Device
        buf.extend(self._write_text_record({
            'RECORD': '41',
            'OwnerIndex': '0',
            'IndexInSheet': '2',
            'OwnerPartId': '-1',
            'FontID': '2',
            'IsHidden': 'T',
            'Text': sym.name,
            'Name': 'Device',
        }))

        # LCSC Part Name - 只填原始description
        if sym.description:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '3',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.description,
                'Name': 'LCSC Part Name',
            }))

        # RECORD=41: Value
        if sym.value:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '3',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.value,
                'Name': 'Value',
            }))

        # RECORD=41: Supplier Part
        if sym.supplier_part:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '4',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.supplier_part,
                'Name': 'Supplier Part',
            }))

        # RECORD=41: Manufacturer
        if sym.manufacturer:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '5',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.manufacturer,
                'Name': 'Manufacturer',
            }))

        # RECORD=41: Manufacturer Part
        if sym.name:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '6',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.name,
                'Name': 'Manufacturer Part',
            }))

        # RECORD=41: Supplier Footprint
        if sym.package:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '7',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.package,
                'Name': 'Supplier Footprint',
            }))

        # RECORD=41: Supplier
        if sym.supplier:
            buf.extend(self._write_text_record({
                'RECORD': '41',
                'OwnerIndex': '0',
                'IndexInSheet': '9',
                'OwnerPartId': '-1',
                'FontID': '2',
                'IsHidden': 'T',
                'Text': sym.supplier,
                'Name': 'Supplier',
            }))

        return bytes(buf)

    @staticmethod
    def _safe_name(name: str) -> str:
        s = name.replace('/', '_').replace('\\', '_')
        return s[:31]

    @staticmethod
    def _build_storage_stream() -> bytes:
        """AltiumSharp: WriteStorage - use template from RC.SchLib"""
        template = _get_sch_storage()
        if template:
            return template
        # Fallback
        return _write_cstring_param_block({'HEADER': 'Icon storage', 'WEIGHT': '0'})

    def _build_cfb(self, symbols: List[SchSymbol],
                    storage_names: List[str],
                    existing_raw: dict = None) -> CfbWriter:
        cfb = CfbWriter()

        all_sn = list((existing_raw or {}).keys()) + storage_names

        cfb.add_stream('FileHeader', self._make_file_header(all_sn))
        cfb.add_stream('Storage', self._build_storage_stream())

        # Write back existing components
        if existing_raw:
            for sn, streams in existing_raw.items():
                for stream_name, data in streams.items():
                    cfb.add_stream(f'{sn}/{stream_name}', data)

        # Write new symbols (Data stream only, no Header stream)
        for sym, sn in zip(symbols, storage_names):
            cfb.add_stream(f'{sn}/Data', self._build_component_data(sym, sn))

        return cfb

    def write(self, filename: str, symbols: List[SchSymbol]):
        storage_names = [self._safe_name(s.name) for s in symbols]
        cfb = self._build_cfb(symbols, storage_names)
        cfb.save(filename)

    def append(self, filename: str, symbols: List[SchSymbol]):
        import olefile

        existing_raw = {}
        existing_names = set()

        if os.path.exists(filename):
            ole = olefile.OleFileIO(filename)
            for entry in ole.listdir(storages=True):
                if len(entry) == 1 and entry[0] not in ('FileHeader', 'SectionKeys', 'Storage'):
                    cn = entry[0]
                    if cn not in existing_names:
                        existing_names.add(cn)
            for name in existing_names:
                existing_raw[name] = {}
                for sn in ('Data',):
                    try:
                        existing_raw[name][sn] = ole.openstream(
                            f'{name}/{sn}').read()
                    except Exception:
                        pass
            ole.close()

        new_syms, new_sns = [], []
        for sym in symbols:
            sn = self._safe_name(sym.name)
            if sn in existing_names:
                print(f"  Skipping existing symbol: {sn}")
                continue
            new_syms.append(sym)
            new_sns.append(sn)

        cfb = self._build_cfb(new_syms, new_sns, existing_raw)
        cfb.save(filename)


# ============================================================
# LibPkg 项目文件生成
# ============================================================

class LibPkgWriter:
    @staticmethod
    def write(filename: str, schlib_name: str, pcblib_name: str):
        content = (
            "[Design]\r\n"
            f"Version=1.0\r\n"
            f"HierarchyMode=0\r\n"
            f"ChannelRoomNamingStyle=0\r\n"
            f"\r\n"
            f"[Document1]\r\n"
            f"DocumentPath={schlib_name}\r\n"
            f"AnnotationEnabled=1\r\n"
            f"AnnotateStartValue=1\r\n"
            f"AnnotationIndexControlEnabled=0\r\n"
            f"AnnotateSuffix=\r\n"
            f"AnnotateScope=All\r\n"
            f"AnnotateOrder=-1\r\n"
            f"\r\n"
            f"[Document2]\r\n"
            f"DocumentPath={pcblib_name}\r\n"
            f"AnnotationEnabled=1\r\n"
            f"AnnotateStartValue=1\r\n"
            f"AnnotationIndexControlEnabled=0\r\n"
            f"AnnotateSuffix=\r\n"
            f"AnnotateScope=All\r\n"
            f"AnnotateOrder=-1\r\n"
        )
        with open(filename, 'wb') as f:
            f.write(content.encode('ascii'))


# ============================================================
# 主程序
# ============================================================

def main():
    ap = argparse.ArgumentParser(
        description='LCSC -> Altium Designer SchLib + PcbLib + LibPkg',
        epilog='Example: python jlc2ad.py C15850 C25804 -o my_lib')
    ap.add_argument('parts', nargs='+', help='LCSC part number (e.g. C15850)')
    ap.add_argument('-o', '--output', default='output',
                    help='Output base name, e.g. "my_lib" -> my_lib.SchLib + my_lib.PcbLib + my_lib.LibPkg')
    args = ap.parse_args()

    base = args.output
    for ext in ('.PcbLib', '.SchLib', '.LibPkg', '.IntLib'):
        if base.lower().endswith(ext.lower()):
            base = base[:-len(ext)]
            break

    pcblib_path = base + '.PcbLib'
    schlib_path = base + '.SchLib'
    libpkg_path = base + '.LibPkg'

    client = EasyEDAClient()
    fp_parser = FootprintParser()
    sch_parser = SchematicParser()
    pcb_writer = PcbLibWriter()
    sch_writer = SchLibWriter()

    footprints = []
    symbols = []

    for pid in args.parts:
        print(f"Fetching {pid} ...")
        try:
            data = client.fetch(pid)
            print(f"  Component: {data['title']} ({data['package_name']})")

            fp = fp_parser.parse(data)
            # 增强描述: 包含 LCSC 编号
            full_desc = f"{data['description']} [{pid}]" if data['description'] else pid
            fp.description = full_desc
            # Parameters中的各个字段
            fp.value = data.get('value', '')
            fp.manufacturer = data.get('manufacturer', '')
            print(f"  PCB: {len(fp.pads)} pads, "
                  f"{len(fp.tracks)} tracks, {len(fp.arcs)} arcs")
            footprints.append(fp)

            sym = sch_parser.parse(data)
            if sym:
                # name (Design Item ID) = 商品型号 (title)
                sym.name = data.get('title', fp.name)
                sym.description = full_desc
                # comment 已经由 sch_parser.parse 设置为 lcsc_id
                print(f"  SCH: {len(sym.pins)} pins, "
                      f"{len(sym.lines)} lines, {len(sym.rects)} rects")
                symbols.append(sym)
            else:
                print(f"  SCH: no schematic data, skipping symbol")
        except Exception as e:
            print(f"  Error: {e}")
            continue

    if not footprints:
        print("No components fetched. Exiting.")
        sys.exit(1)

    if os.path.exists(pcblib_path):
        print(f"\n{pcblib_path} exists, appending...")
        pcb_writer.append(pcblib_path, footprints)
    else:
        print(f"\nCreating {pcblib_path} ...")
        pcb_writer.write(pcblib_path, footprints)
    print(f"  {len(footprints)} footprint(s)")

    if symbols:
        if os.path.exists(schlib_path):
            print(f"\n{schlib_path} exists, appending...")
            sch_writer.append(schlib_path, symbols)
        else:
            print(f"\nCreating {schlib_path} ...")
            sch_writer.write(schlib_path, symbols)
        print(f"  {len(symbols)} symbol(s)")

    pcb_basename = os.path.basename(pcblib_path)
    sch_basename = os.path.basename(schlib_path)
    LibPkgWriter.write(libpkg_path, sch_basename, pcb_basename)
    print(f"\nCreating {libpkg_path} ...")

    print(f"\nDone! Files created:")
    print(f"  {pcblib_path}")
    if symbols:
        print(f"  {schlib_path}")
    print(f"  {libpkg_path}")
    print(f"\nTo create IntLib: Open {libpkg_path} in AD24 -> Project -> Compile Integrated Library")


if __name__ == '__main__':
    main()
