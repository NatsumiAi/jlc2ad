import json
from typing import Iterable, List, Sequence, Tuple


Point = Tuple[float, float]


def parse_shape_payload(raw: str):
    text = (raw or '').strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_path_points(value) -> List[Point]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    if _is_rect_payload(value):
        x, y, width, height = _float(value[1]), _float(value[2]), _float(value[3]), _float(value[4])
        return _dedupe([(x, y), (x + width, y), (x + width, y - height), (x, y - height), (x, y)])

    points: List[Point] = []
    index = 0
    while index < len(value):
        item = value[index]
        if _is_number(item):
            if index + 1 < len(value) and _is_number(value[index + 1]):
                points.append((_float(item), _float(value[index + 1])))
                index += 2
                continue
        elif isinstance(item, str):
            command = item.upper()
            if command == 'L':
                index += 1
                while index + 1 < len(value) and _is_number(value[index]) and _is_number(value[index + 1]):
                    points.append((_float(value[index]), _float(value[index + 1])))
                    index += 2
                continue
            if command in ('A', 'ARC') and index + 2 < len(value):
                if _is_number(value[index + 1]) and _is_number(value[index + 2]):
                    points.append((_float(value[index + 1]), _float(value[index + 2])))
                    index += 3
                    continue
        index += 1
    return _dedupe(points)


def parse_circle_payload(value):
    if not isinstance(value, Sequence) or len(value) < 4 or not isinstance(value[0], str):
        return None
    if value[0].upper() != 'CIRCLE':
        return None
    return _float(value[1]), _float(value[2]), _float(value[3])


def is_axis_aligned_rectangle(points: Iterable[Point]) -> bool:
    pts = list(points)
    if len(pts) == 5 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) != 4:
        return False
    xs = {point[0] for point in pts}
    ys = {point[1] for point in pts}
    return len(xs) == 2 and len(ys) == 2


def _is_rect_payload(value) -> bool:
    return len(value) >= 5 and isinstance(value[0], str) and value[0].upper() == 'R'


def _dedupe(points: List[Point]) -> List[Point]:
    result: List[Point] = []
    for point in points:
        if not result or result[-1] != point:
            result.append(point)
    return result


def _is_number(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


__all__ = ['is_axis_aligned_rectangle', 'parse_circle_payload', 'parse_path_points', 'parse_shape_payload']
