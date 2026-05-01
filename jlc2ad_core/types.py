from dataclasses import dataclass, field
from typing import Dict, List

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
class Model3D:
    uuid: str = ""
    name: str = ""
    title: str = ""
    path: str = ""
    step_url: str = ""
    obj_url: str = ""
    translation_x: float = 0.0
    translation_y: float = 0.0
    translation_z: float = 0.0
    translation_unit: str = "easyeda"
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    rotation_unit: str = "degree"
    width: float = 0.0
    height: float = 0.0
    size_unit: str = "easyeda"
    raw_shape: str = ""
    transform_raw: str = ""
    transform: Dict[str, object] = field(default_factory=dict)
    step_path: str = ""
    obj_path: str = ""
    obj_min_z: float = 0.0
    obj_max_z: float = 0.0
    obj_height_mm: float = 0.0
    obj_unit: str = "obj"
    bbox_min_x: float = 0.0
    bbox_min_y: float = 0.0
    bbox_max_x: float = 0.0
    bbox_max_y: float = 0.0
    bbox_unit: str = "altium_internal"
    footprint_center_x: float = 0.0
    footprint_center_y: float = 0.0
    altium_offset_x: float = 0.0
    altium_offset_y: float = 0.0
    altium_offset_z: float = 0.0
    altium_offset_unit: str = "altium_internal"
    footprint_center_x_mm: float = 0.0
    footprint_center_y_mm: float = 0.0
    bbox_min_x_mm: float = 0.0
    bbox_min_y_mm: float = 0.0
    bbox_max_x_mm: float = 0.0
    bbox_max_y_mm: float = 0.0
    translation_x_mm: float = 0.0
    translation_y_mm: float = 0.0
    translation_z_mm: float = 0.0
    width_mm: float = 0.0
    height_mm: float = 0.0
    obj_min_z_mm: float = 0.0
    node_bbox_min_x: float = 0.0
    node_bbox_min_y: float = 0.0
    node_bbox_max_x: float = 0.0
    node_bbox_max_y: float = 0.0
    node_center_x: float = 0.0
    node_center_y: float = 0.0
    node_bbox_width: float = 0.0
    node_bbox_height: float = 0.0
    inferred_scale_x: float = 0.0
    inferred_scale_y: float = 0.0
    inferred_scale: float = 0.0
    placement_source: str = ""
    recommended_rotation_source: str = ""
    recommended_rotation_x: float = 0.0
    recommended_rotation_y: float = 0.0
    recommended_rotation_z: float = 0.0
    placement_x_mm: float = 0.0
    placement_y_mm: float = 0.0
    placement_z_mm: float = 0.0
    metadata_path: str = ""

@dataclass
class Footprint:
    name: str = ""
    description: str = ""
    height: str = "0mil"
    package: str = ""
    value: str = ""
    manufacturer: str = ""
    manufacturer_part: str = ""
    supplier_part: str = ""
    supplier: str = "LCSC"
    datasheet: str = ""
    jlcpcb_part_class: str = ""
    symbol_name: str = ""
    lcsc_part_name: str = ""
    model_3d_name: str = ""
    model_3d_title: str = ""
    model_3d_uuid: str = ""
    model_3d_transform: str = ""
    model_3d: Model3D | None = None
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
    manufacturer_part: str = ""  # 厂商型号
    value: str = ""  # 值
    supplier_part: str = ""  # 供应商型号
    supplier: str = "LCSC"  # 供应商
    datasheet: str = ""
    jlcpcb_part_class: str = ""
    symbol_name: str = ""
    lcsc_part_name: str = ""
    model_3d_name: str = ""
    model_3d_title: str = ""
    model_3d_uuid: str = ""
    model_3d_transform: str = ""
    pins: List[SchPin] = field(default_factory=list)
    lines: List[SchLine] = field(default_factory=list)
    rects: List[SchRect] = field(default_factory=list)
    arcs: List[SchArc] = field(default_factory=list)


# ============================================================
# EasyEDA API 客户端
# ============================================================

