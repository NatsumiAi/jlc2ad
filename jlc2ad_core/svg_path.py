import re
from typing import List, Optional, Tuple


SVG_ARC_RE = re.compile(
    r'M\s*([\d.\-]+)\s+([\d.\-]+)\s+A\s*([\d.\-]+)\s+([\d.\-]+)\s+'
    r'[\d.\-]+\s+([01])\s+([01])\s+([\d.\-]+)\s+([\d.\-]+)',
    flags=re.IGNORECASE,
)


def parse_svg_arc(path: str) -> Optional[Tuple[float, float, float, float, int, int, float, float]]:
    normalized = path.replace(',', ' ')
    match = SVG_ARC_RE.search(normalized)
    if not match:
        return None
    return (
        float(match.group(1)),
        float(match.group(2)),
        float(match.group(3)),
        float(match.group(4)),
        int(match.group(5)),
        int(match.group(6)),
        float(match.group(7)),
        float(match.group(8)),
    )


def pin_length_from_path(path: str, default: int = 20) -> int:
    match = re.match(r'M\s*[\d.\-,]+[\s,][\d.\-]+\s*h\s*([\d.\-]+)', path, flags=re.IGNORECASE)
    if match:
        return abs(int(round(float(match.group(1)))))
    match = re.match(r'M\s*[\d.\-,]+[\s,][\d.\-]+\s*v\s*([\d.\-]+)', path, flags=re.IGNORECASE)
    if match:
        return abs(int(round(float(match.group(1)))))
    return default


def path_line_points(path: str) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    tokens = re.findall(r'[MLZ]|-?\d+(?:\.\d+)?', path, flags=re.IGNORECASE)
    if not tokens:
        return []

    segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    index = 0
    current = None
    start = None
    cmd = ''

    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if upper in ('M', 'L', 'Z'):
            cmd = upper
            index += 1
            if cmd == 'Z' and current is not None and start is not None:
                segments.append((current, start))
                current = start
            continue

        if cmd in ('M', 'L') and index + 1 < len(tokens):
            try:
                x = float(tokens[index])
                y = float(tokens[index + 1])
            except ValueError:
                index += 1
                continue

            if cmd == 'M':
                current = (x, y)
                start = (x, y)
                cmd = 'L'
            else:
                if current is not None:
                    segments.append((current, (x, y)))
                current = (x, y)
            index += 2
        else:
            index += 1

    return segments


__all__ = ['parse_svg_arc', 'pin_length_from_path', 'path_line_points']
