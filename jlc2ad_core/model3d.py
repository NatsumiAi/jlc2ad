from __future__ import annotations

import json
import math
import os
from dataclasses import asdict
from typing import Iterable, Optional

from .geometry import CoordinateTransformer
from .types import UNIT_SCALE
from .types import Arc, Footprint, Model3D
from .writer_common import _safe_storage_name


EASYEDA_PCB_UNIT_TO_MM = 0.254
ALTIUM_INTERNAL_TO_MM = 0.00000254


def parse_3d_model_shape(shape_str: str) -> Optional[Model3D]:
    parts = shape_str.split('~')
    if not parts or parts[0] != 'SVGNODE':
        return None

    attrs = _extract_json_mapping(parts)
    if not attrs:
        return None

    uuid = _first_text(
        attrs.get('uuid'),
        attrs.get('modelId'),
        attrs.get('modelUuid'),
        attrs.get('attrs', {}).get('uuid') if isinstance(attrs.get('attrs'), dict) else None,
    )
    if not uuid:
        return None

    node_attrs = attrs.get('attrs') if isinstance(attrs.get('attrs'), dict) else attrs
    origin = _parse_csv_floats(node_attrs.get('c_origin'))
    rotation = _parse_csv_floats(node_attrs.get('c_rotation'))

    model = Model3D(
        uuid=uuid,
        name=_first_text(node_attrs.get('title'), attrs.get('title')),
        title=_first_text(node_attrs.get('title'), attrs.get('title')),
        path=_first_text(node_attrs.get('src'), attrs.get('src')),
        translation_x=_float_at(origin, 0),
        translation_y=_float_at(origin, 1),
        translation_z=_float_value(node_attrs.get('z')),
        rotation_x=_float_at(rotation, 0),
        rotation_y=_float_at(rotation, 1),
        rotation_z=_float_at(rotation, 2),
        width=_float_value(node_attrs.get('c_width')),
        height=_float_value(node_attrs.get('c_height')),
        raw_shape=shape_str,
    )
    _apply_node_bounds(model, attrs)
    return model


def enrich_model_urls(model: Model3D) -> Model3D:
    if not model.uuid:
        return model
    model.step_url = f'https://modules.easyeda.com/qAxj6KHrDKw4blvCG8QJPs7Y/{model.uuid}'
    model.obj_url = f'https://modules.easyeda.com/3dmodel/{model.uuid}'
    return model


def parse_obj_min_z(text: str) -> float:
    min_z, _, _ = parse_obj_z_bounds(text)
    return min_z


def parse_obj_z_bounds(text: str) -> tuple[float, float, float]:
    min_z = None
    max_z = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith('v '):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            z = float(parts[3])
        except ValueError:
            continue
        min_z = z if min_z is None else min(min_z, z)
        max_z = z if max_z is None else max(max_z, z)
    if min_z is None or max_z is None:
        return 0.0, 0.0, 0.0
    return min_z, max_z, max_z - min_z


def apply_footprint_placement(model: Model3D, footprint: Footprint) -> Model3D:
    bounds = footprint_bounds(footprint)
    if bounds is None:
        return model

    min_x, min_y, max_x, max_y = bounds
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0

    model.bbox_min_x = min_x
    model.bbox_min_y = min_y
    model.bbox_max_x = max_x
    model.bbox_max_y = max_y
    model.footprint_center_x = center_x
    model.footprint_center_y = center_y
    model.bbox_min_x_mm = altium_internal_to_mm(min_x)
    model.bbox_min_y_mm = altium_internal_to_mm(min_y)
    model.bbox_max_x_mm = altium_internal_to_mm(max_x)
    model.bbox_max_y_mm = altium_internal_to_mm(max_y)
    model.footprint_center_x_mm = altium_internal_to_mm(center_x)
    model.footprint_center_y_mm = altium_internal_to_mm(center_y)

    inferred_scale_x = 0.0
    inferred_scale_y = 0.0
    transform_size_x = _nested_float(model.transform, 'size', 'x')
    transform_size_y = _nested_float(model.transform, 'size', 'y')
    transform_offset_x = _nested_float(model.transform, 'offset', 'x')
    transform_offset_y = _nested_float(model.transform, 'offset', 'y')
    transform_offset_z = _nested_float(model.transform, 'offset', 'z')
    transform_rotation_x = _nested_float(model.transform, 'rotation', 'x')
    transform_rotation_y = _nested_float(model.transform, 'rotation', 'y')
    transform_rotation_z = _nested_float(model.transform, 'rotation', 'z')

    if model.node_bbox_width and transform_size_x:
        inferred_scale_x = transform_size_x / model.node_bbox_width
    elif model.node_bbox_width:
        inferred_scale_x = (model.bbox_max_x_mm - model.bbox_min_x_mm) / model.node_bbox_width

    if model.node_bbox_height and transform_size_y:
        inferred_scale_y = transform_size_y / model.node_bbox_height
    elif model.node_bbox_height:
        inferred_scale_y = (model.bbox_max_y_mm - model.bbox_min_y_mm) / model.node_bbox_height
    inferred_scale = inferred_scale_x or inferred_scale_y or EASYEDA_PCB_UNIT_TO_MM
    if inferred_scale_x and inferred_scale_y:
        inferred_scale = (inferred_scale_x + inferred_scale_y) / 2.0

    model.inferred_scale_x = inferred_scale_x
    model.inferred_scale_y = inferred_scale_y
    model.inferred_scale = inferred_scale

    model.translation_x_mm = model.translation_x * inferred_scale
    model.translation_y_mm = model.translation_y * inferred_scale
    model.translation_z_mm = model.translation_z * inferred_scale
    model.width_mm = transform_size_x or (model.width * inferred_scale)
    model.height_mm = transform_size_y or (model.height * inferred_scale)
    model.obj_min_z_mm = model.obj_min_z
    if model.obj_height_mm:
        model.height_mm = model.obj_height_mm

    if transform_size_x or transform_size_y:
        model.placement_source = 'transform_offset'
        model.placement_x_mm = transform_offset_x
        model.placement_y_mm = -transform_offset_y
        model.placement_z_mm = transform_offset_z + abs(model.obj_min_z_mm)
        model.recommended_rotation_source = 'transform_rotation'
        model.recommended_rotation_x = transform_rotation_x
        model.recommended_rotation_y = transform_rotation_y
        model.recommended_rotation_z = transform_rotation_z
    elif model.node_bbox_width or model.node_bbox_height:
        model.placement_source = 'svgnode_bbox_scale'
        model.placement_x_mm = (model.translation_x - model.node_center_x) * inferred_scale
        model.placement_y_mm = (model.node_center_y - model.translation_y) * inferred_scale
        model.placement_z_mm = model.translation_z_mm + abs(model.obj_min_z_mm)
        model.recommended_rotation_source = 'svgnode_rotation'
        model.recommended_rotation_x = model.rotation_x
        model.recommended_rotation_y = model.rotation_y
        model.recommended_rotation_z = model.rotation_z
    else:
        model.placement_source = 'fallback_easyeda_scale'
        model.placement_x_mm = model.translation_x_mm - model.footprint_center_x_mm
        model.placement_y_mm = model.footprint_center_y_mm - model.translation_y_mm
        model.placement_z_mm = model.translation_z_mm + abs(model.obj_min_z_mm)
        model.recommended_rotation_source = 'svgnode_rotation'
        model.recommended_rotation_x = model.rotation_x
        model.recommended_rotation_y = model.rotation_y
        model.recommended_rotation_z = model.rotation_z

    model.altium_offset_x = mm_to_altium_internal(model.placement_x_mm)
    model.altium_offset_y = mm_to_altium_internal(model.placement_y_mm)
    model.altium_offset_z = mm_to_altium_internal(model.placement_z_mm)
    return model


def save_model_metadata(model: Model3D, output_dir: str, part_id: str, footprint_name: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    file_name = f'{_safe_storage_name(part_id)}_{_safe_storage_name(footprint_name)}_3d.json'
    metadata_path = os.path.join(output_dir, file_name)
    with open(metadata_path, 'w', encoding='utf-8') as file:
        json.dump(asdict(model), file, ensure_ascii=False, indent=2)
    return metadata_path


def model_output_dir(base_name: str) -> str:
    safe_base = _safe_storage_name(base_name) or 'output'
    return os.path.join('artifacts', safe_base, '3dmodels')


def footprint_bounds(footprint: Footprint) -> Optional[tuple[float, float, float, float]]:
    xs: list[float] = []
    ys: list[float] = []

    for pad in footprint.pads:
        half_x = pad.size_x / 2.0
        half_y = pad.size_y / 2.0
        xs.extend([pad.x - half_x, pad.x + half_x])
        ys.extend([pad.y - half_y, pad.y + half_y])

    for track in footprint.tracks:
        half_width = track.width / 2.0
        xs.extend([track.x1 - half_width, track.x1 + half_width, track.x2 - half_width, track.x2 + half_width])
        ys.extend([track.y1 - half_width, track.y1 + half_width, track.y2 - half_width, track.y2 + half_width])

    for arc in footprint.arcs:
        _extend_arc_bounds(xs, ys, arc)

    for fill in footprint.fills:
        xs.extend([fill.x1, fill.x2])
        ys.extend([fill.y1, fill.y2])

    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def easyeda_pcb_to_mm(value: float) -> float:
    return value * EASYEDA_PCB_UNIT_TO_MM


def mm_to_altium_internal(value_mm: float) -> float:
    return value_mm / ALTIUM_INTERNAL_TO_MM


def altium_internal_to_mm(value: float) -> float:
    return value * ALTIUM_INTERNAL_TO_MM


def _extend_arc_bounds(xs: list[float], ys: list[float], arc: Arc) -> None:
    samples = [arc.start_angle, arc.end_angle]
    start = arc.start_angle % 360
    end = arc.end_angle % 360
    for angle in (0.0, 90.0, 180.0, 270.0):
        if _angle_in_arc(angle, start, end):
            samples.append(angle)
    half_width = arc.width / 2.0
    for angle in samples:
        radians = math.radians(angle)
        x = arc.center_x + arc.radius * math.cos(radians)
        y = arc.center_y - arc.radius * math.sin(radians)
        xs.extend([x - half_width, x + half_width])
        ys.extend([y - half_width, y + half_width])


def _angle_in_arc(angle: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def _extract_json_mapping(parts: Iterable[str]) -> dict:
    for part in parts:
        text = part.strip()
        if not text or '{' not in text or '}' not in text:
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _apply_node_bounds(model: Model3D, node: dict) -> None:
    child_nodes = node.get('childNodes')
    if not isinstance(child_nodes, list):
        return

    xs: list[float] = []
    ys: list[float] = []
    for child in child_nodes:
        if not isinstance(child, dict):
            continue
        attrs = child.get('attrs') if isinstance(child.get('attrs'), dict) else {}
        _collect_child_points(xs, ys, attrs)

    if not xs or not ys:
        return

    model.node_bbox_min_x = min(xs)
    model.node_bbox_min_y = min(ys)
    model.node_bbox_max_x = max(xs)
    model.node_bbox_max_y = max(ys)
    model.node_center_x = (model.node_bbox_min_x + model.node_bbox_max_x) / 2.0
    model.node_center_y = (model.node_bbox_min_y + model.node_bbox_max_y) / 2.0
    model.node_bbox_width = model.node_bbox_max_x - model.node_bbox_min_x
    model.node_bbox_height = model.node_bbox_max_y - model.node_bbox_min_y


def _collect_child_points(xs: list[float], ys: list[float], attrs: dict) -> None:
    for key in ('points', 'd', 'path'):
        raw = attrs.get(key)
        if not raw:
            continue
        numbers = _extract_numeric_values(str(raw))
        if len(numbers) < 2:
            continue
        for index in range(0, len(numbers) - 1, 2):
            xs.append(numbers[index])
            ys.append(numbers[index + 1])
        return

    for x_key, y_key in (('cx', 'cy'), ('x', 'y'), ('x1', 'y1')):
        if x_key in attrs and y_key in attrs:
            xs.append(_float_value(attrs.get(x_key)))
            ys.append(_float_value(attrs.get(y_key)))


def _extract_numeric_values(text: str) -> list[float]:
    values: list[float] = []
    current = ''
    for char in text:
        if char.isdigit() or char in '.-+eE':
            current += char
            continue
        if current:
            try:
                values.append(float(current))
            except ValueError:
                pass
            current = ''
    if current:
        try:
            values.append(float(current))
        except ValueError:
            pass
    return values


def _nested_float(root: dict, *keys: str) -> float:
    current = root
    for key in keys:
        if not isinstance(current, dict):
            return 0.0
        current = current.get(key)
    return _float_value(current)


def _parse_csv_floats(raw: object) -> list[float]:
    if raw is None:
        return []
    values = []
    for part in str(raw).split(','):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(float(part))
        except ValueError:
            return []
    return values


def _float_value(value: object) -> float:
    try:
        return float(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _float_at(values: list[float], index: int) -> float:
    if index < len(values):
        return values[index]
    return 0.0


def _first_text(*values: object) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ''


__all__ = [
    'apply_footprint_placement',
    'enrich_model_urls',
    'footprint_bounds',
    'model_output_dir',
    'parse_3d_model_shape',
    'parse_obj_min_z',
    'parse_obj_z_bounds',
    'save_model_metadata',
]
