import os
import re
import struct


def _resource_path(filename: str) -> str:
    module_dir = os.path.dirname(__file__)
    candidates = [
        os.path.join(module_dir, filename),
        os.path.join(os.path.dirname(module_dir), filename),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[-1]


def _write_string_block(name: str) -> bytes:
    data = name.encode('ascii', errors='replace')
    buf = struct.pack('<I', 1 + len(data))
    buf += struct.pack('B', len(data))
    buf += data
    return buf


def _write_cstring_param_block(params: dict) -> bytes:
    text = ''.join(f"|{k}={v}" for k, v in params.items())
    try:
        data = text.encode('gbk') + b'\x00'
    except UnicodeEncodeError:
        data = text.encode('utf-8', errors='replace') + b'\x00'
    return struct.pack('<I', len(data)) + data


def _safe_storage_name(name: str) -> str:
    return re.sub(r'[^0-9A-Za-z_\- ]', '_', name)[:31]


def _load_file_header() -> bytes:
    header_file = _resource_path('pcb_file_header.bin')
    if os.path.exists(header_file):
        with open(header_file, 'rb') as file:
            return file.read()
    return None


def _load_library_params() -> str:
    params_file = _resource_path('pcb_library_params.txt')
    if os.path.exists(params_file):
        with open(params_file, 'r', encoding='utf-8') as file:
            return file.read()
    return None


def _load_sch_file_header() -> bytes:
    header_file = _resource_path('sch_file_header.bin')
    if os.path.exists(header_file):
        with open(header_file, 'rb') as file:
            return file.read()
    return None


def _load_sch_storage() -> bytes:
    storage_file = _resource_path('sch_storage.bin')
    if os.path.exists(storage_file):
        with open(storage_file, 'rb') as file:
            return file.read()
    return None


PCB_FILE_HEADER_TEMPLATE = None
PCB_LIBRARY_PARAMS_TEMPLATE = None
SCH_FILE_HEADER_TEMPLATE = None
SCH_STORAGE_TEMPLATE = None


def _get_file_header() -> bytes:
    global PCB_FILE_HEADER_TEMPLATE
    if PCB_FILE_HEADER_TEMPLATE is None:
        PCB_FILE_HEADER_TEMPLATE = _load_file_header()
    return PCB_FILE_HEADER_TEMPLATE


def _get_library_params() -> str:
    global PCB_LIBRARY_PARAMS_TEMPLATE
    if PCB_LIBRARY_PARAMS_TEMPLATE is None:
        PCB_LIBRARY_PARAMS_TEMPLATE = _load_library_params()
    return PCB_LIBRARY_PARAMS_TEMPLATE


def _get_sch_file_header() -> bytes:
    global SCH_FILE_HEADER_TEMPLATE
    if SCH_FILE_HEADER_TEMPLATE is None:
        SCH_FILE_HEADER_TEMPLATE = _load_sch_file_header()
    return SCH_FILE_HEADER_TEMPLATE


def _get_sch_storage() -> bytes:
    global SCH_STORAGE_TEMPLATE
    if SCH_STORAGE_TEMPLATE is None:
        SCH_STORAGE_TEMPLATE = _load_sch_storage()
    return SCH_STORAGE_TEMPLATE


__all__ = [
    '_resource_path',
    '_write_string_block',
    '_write_cstring_param_block',
    '_safe_storage_name',
    '_get_file_header',
    '_get_library_params',
    '_get_sch_file_header',
    '_get_sch_storage',
]
