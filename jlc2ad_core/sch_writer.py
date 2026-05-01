import os
import re
import struct
from typing import List

from .cfb_writer import CfbWriter
from .types import SchPin, SchSymbol
from .writer_common import _get_sch_file_header, _get_sch_storage, _safe_storage_name, _write_cstring_param_block, _write_string_block


class SchLibWriter:
    def _append_hidden_parameter(self, buf: bytearray, index: int, name: str, text: str):
        if not text:
            return
        buf.extend(self._write_text_record({
            'RECORD': '41',
            'OwnerIndex': '0',
            'IndexInSheet': str(index),
            'OwnerPartId': '-1',
            'FontID': '2',
            'IsHidden': 'T',
            'Text': text,
            'Name': name,
        }))

    def _make_file_header(self, storage_names: List[str]) -> bytes:
        template = _get_sch_file_header()
        if template:
            return re.sub(rb'\|Weight=\d+', f'|Weight={len(storage_names)}'.encode(), template)

        buf = bytearray()
        buf.extend(_write_cstring_param_block({
            'HEADER': 'Protel for Windows - Schematic Library Editor Binary File Version 5.0',
            'Weight': str(len(storage_names)),
        }))
        buf.extend(struct.pack('<i', len(storage_names)))
        for storage_name in storage_names:
            buf.extend(_write_string_block(storage_name))
        return bytes(buf)

    def _write_text_record(self, params: dict) -> bytes:
        return _write_cstring_param_block(params)

    def _write_pin_binary(self, pin: SchPin) -> bytes:
        data = bytearray()
        data.extend(struct.pack('<i', 2))
        data.append(0)
        data.extend(struct.pack('<h', 1))
        data.append(0)
        data.append(0)
        data.append(0)
        data.append(0)
        data.append(0)
        data.append(0)
        data.append(0)
        data.append(pin.electrical & 0xFF)
        conglomerate = (pin.orientation & 0x03) | 0x08 | 0x20
        data.append(conglomerate)
        data.extend(struct.pack('<h', pin.length))
        data.extend(struct.pack('<h', pin.x))
        data.extend(struct.pack('<h', pin.y))
        data.extend(struct.pack('<i', 128))
        name_b = pin.name.encode('ascii', errors='replace')
        data.append(len(name_b))
        data.extend(name_b)
        des_b = pin.number.encode('ascii', errors='replace')
        data.append(len(des_b))
        data.extend(des_b)
        data.append(0)
        swap = b'|&|'
        data.append(len(swap))
        data.extend(swap)
        data.append(0)

        length = len(data)
        size_word = (0x01 << 24) | length
        return struct.pack('<I', size_word) + bytes(data)

    def _build_component_data(self, sym: SchSymbol, storage_name: str) -> bytes:
        buf = bytearray()
        component_desc = sym.description if sym.description else sym.name

        buf.extend(self._write_text_record({
            'RECORD': '1',
            'LibReference': storage_name,
            'ComponentDescription': component_desc,
            'PartCount': '1',
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

        for pin in sym.pins:
            buf.extend(self._write_pin_binary(pin))

        if sym.package:
            import uuid

            model_uid = uuid.uuid4().hex[:12].upper()
            model_name = _safe_storage_name(sym.package)
            model_owner = len(sym.pins) + 5
            model_child_owner = model_owner + 1

            buf.extend(self._write_text_record({
                'RECORD': '45',
                'OwnerIndex': str(model_owner),
                'IndexInSheet': '-1',
                'Description': model_name,
                'ModelName': model_name,
                'ModelType': 'PCBLIB',
                'DatafileCount': '1',
                'ModelDatafileEntity0': model_name,
                'ModelDatafileKind0': 'PCBLib',
                'IsCurrent': 'T',
                'IntegratedModel': 'T',
                'DatabaseModel': 'T',
                'UniqueID': model_uid,
            }))
            buf.extend(self._write_text_record({
                'RECORD': '46',
                'OwnerIndex': str(model_child_owner),
            }))
            buf.extend(self._write_text_record({
                'RECORD': '48',
                'OwnerIndex': str(model_child_owner),
            }))

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

        hidden_params = [
            ('LCSC Part Name', sym.description),
            ('Value', sym.value),
            ('Supplier Part', sym.supplier_part),
            ('Manufacturer', sym.manufacturer),
            ('Manufacturer Part', sym.manufacturer_part if sym.manufacturer_part else sym.name),
            ('Supplier Footprint', sym.package),
            ('Supplier', sym.supplier),
            ('Datasheet', getattr(sym, 'datasheet', '')),
            ('JLCPCB Part Class', getattr(sym, 'jlcpcb_part_class', '')),
            ('LCSC Part', sym.comment),
            ('Symbol', getattr(sym, 'symbol_name', sym.name)),
            ('Footprint', sym.package),
            ('3D Model Name', getattr(sym, 'model_3d_name', '')),
            ('3D Model Title', getattr(sym, 'model_3d_title', '')),
            ('3D Model UUID', getattr(sym, 'model_3d_uuid', '')),
            ('3D Model Transform', getattr(sym, 'model_3d_transform', '')),
        ]
        next_index = 3
        for name, text in hidden_params:
            self._append_hidden_parameter(buf, next_index, name, text)
            if text:
                next_index += 1

        return bytes(buf)

    @staticmethod
    def _safe_name(name: str) -> str:
        return _safe_storage_name(name)

    @staticmethod
    def _build_storage_stream() -> bytes:
        template = _get_sch_storage()
        if template:
            return template
        return _write_cstring_param_block({'HEADER': 'Icon storage', 'WEIGHT': '0'})

    def _build_cfb(self, symbols: List[SchSymbol], storage_names: List[str], existing_raw: dict = None) -> CfbWriter:
        cfb = CfbWriter()
        all_storage_names = list((existing_raw or {}).keys()) + storage_names
        cfb.add_stream('FileHeader', self._make_file_header(all_storage_names))
        cfb.add_stream('Storage', self._build_storage_stream())

        if existing_raw:
            for storage_name, streams in existing_raw.items():
                for stream_name, data in streams.items():
                    cfb.add_stream(f'{storage_name}/{stream_name}', data)

        for symbol, storage_name in zip(symbols, storage_names):
            cfb.add_stream(f'{storage_name}/Data', self._build_component_data(symbol, storage_name))
        return cfb

    def write(self, filename: str, symbols: List[SchSymbol]):
        storage_names = [self._safe_name(symbol.name) for symbol in symbols]
        self._build_cfb(symbols, storage_names).save(filename)

    def append(self, filename: str, symbols: List[SchSymbol]):
        import olefile

        existing_raw = {}
        existing_names = set()
        existing_part_ids = set()

        if os.path.exists(filename):
            ole = olefile.OleFileIO(filename)
            for entry in ole.listdir(storages=True):
                if len(entry) == 1 and entry[0] not in ('FileHeader', 'SectionKeys', 'Storage'):
                    existing_names.add(entry[0])
            for name in existing_names:
                existing_raw[name] = {}
                for stream_name in ('Data',):
                    try:
                        existing_raw[name][stream_name] = ole.openstream(f'{name}/{stream_name}').read()
                    except Exception:
                        pass
                existing_part_ids.update(self._extract_part_ids(existing_raw[name].get('Data', b'')))
            ole.close()

        new_symbols = []
        new_storage_names = []
        for symbol in symbols:
            storage_name = self._safe_name(symbol.name)
            part_id = self._normalized_part_id(getattr(symbol, 'supplier_part', ''))
            if part_id and part_id in existing_part_ids:
                print(f'  Skipping existing symbol part: {part_id}')
                continue
            if storage_name in existing_names:
                print(f'  Skipping existing symbol: {storage_name}')
                continue
            new_symbols.append(symbol)
            new_storage_names.append(storage_name)

        self._build_cfb(new_symbols, new_storage_names, existing_raw).save(filename)

    @classmethod
    def _extract_part_ids(cls, data: bytes) -> set:
        text = data.decode('gbk', errors='ignore')
        found = set()
        for key in ('Supplier Part', 'LCSC Part'):
            value = cls._extract_param_value(text, key)
            normalized = cls._normalized_part_id(value)
            if normalized:
                found.add(normalized)
        return found

    @staticmethod
    def _extract_param_value(text: str, key: str) -> str:
        marker = f'|Name={key}'
        start = text.find(marker)
        if start < 0:
            marker = f'|{key}='
            start = text.find(marker)
            if start < 0:
                return ''
            start += len(marker)
            end = text.find('|', start)
            if end < 0:
                end = len(text)
            return text[start:end].strip('\x00 ').upper()

        text_marker = '|Text='
        text_start = text.find(text_marker, start)
        if text_start < 0:
            return ''
        text_start += len(text_marker)
        end = text.find('|', text_start)
        if end < 0:
            end = len(text)
        return text[text_start:end].strip('\x00 ').upper()

    @staticmethod
    def _normalized_part_id(value: str) -> str:
        value = (value or '').strip().upper()
        match = re.search(r'\bC\d+\b', value)
        return match.group(0) if match else ''


__all__ = ['SchLibWriter']
