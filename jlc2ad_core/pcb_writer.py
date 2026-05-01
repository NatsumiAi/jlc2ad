import os
import re
import struct
import uuid
import zlib
from typing import List

from .cfb_writer import CfbWriter
from .types import PCB_FLAGS_UNLOCKED, Arc, Fill, Footprint, Pad, Region, Track
from .writer_common import _get_file_header, _get_library_params, _safe_storage_name, _write_cstring_param_block, _write_string_block


class RecordPacker:
    def _common_header(self, layer: int, flags: int = PCB_FLAGS_UNLOCKED) -> bytearray:
        header = bytearray(13)
        header[0] = layer & 0xFF
        struct.pack_into('<H', header, 1, flags)
        header[3:13] = b'\xFF' * 10
        return header

    def pack_pad(self, pad: Pad) -> bytes:
        record = bytearray([0x02])

        designator = pad.name.encode('ascii', errors='replace')
        record.extend(struct.pack('<I', 1 + len(designator)))
        record.append(len(designator))
        record.extend(designator)

        record.extend(struct.pack('<I', 1))
        record.append(0)

        net_str = b'|&|0'
        record.extend(struct.pack('<I', 1 + len(net_str)))
        record.append(len(net_str))
        record.extend(net_str)

        record.extend(struct.pack('<I', 1))
        record.append(0)

        pad_data = bytearray(114)
        pad_data[:13] = self._common_header(pad.layer)
        struct.pack_into('<i', pad_data, 13, pad.x)
        struct.pack_into('<i', pad_data, 17, pad.y)
        struct.pack_into('<i', pad_data, 21, pad.size_x)
        struct.pack_into('<i', pad_data, 25, pad.size_y)
        struct.pack_into('<i', pad_data, 29, pad.size_x)
        struct.pack_into('<i', pad_data, 33, pad.size_y)
        struct.pack_into('<i', pad_data, 37, pad.size_x)
        struct.pack_into('<i', pad_data, 41, pad.size_y)
        struct.pack_into('<i', pad_data, 45, pad.hole_size)
        pad_data[49] = pad.shape
        pad_data[50] = pad.shape
        pad_data[51] = pad.shape
        struct.pack_into('<d', pad_data, 52, pad.rotation)
        pad_data[60] = 1 if pad.plated else 0
        struct.pack_into('<h', pad_data, 72, 4)
        record.extend(struct.pack('<I', len(pad_data)))
        record.extend(pad_data)
        record.extend(struct.pack('<I', 0))
        return bytes(record)

    def pack_track(self, track: Track) -> bytes:
        shape_record = bytearray(36)
        shape_record[:13] = self._common_header(track.layer)
        struct.pack_into('<i', shape_record, 13, track.x1)
        struct.pack_into('<i', shape_record, 17, track.y1)
        struct.pack_into('<i', shape_record, 21, track.x2)
        struct.pack_into('<i', shape_record, 25, track.y2)
        struct.pack_into('<i', shape_record, 29, track.width)
        struct.pack_into('<H', shape_record, 33, 0)
        shape_record[35] = 0
        record = bytearray([0x04])
        record.extend(struct.pack('<I', len(shape_record)))
        record.extend(shape_record)
        return bytes(record)

    def pack_arc(self, arc: Arc) -> bytes:
        shape_record = bytearray(45)
        shape_record[:13] = self._common_header(arc.layer)
        struct.pack_into('<i', shape_record, 13, arc.center_x)
        struct.pack_into('<i', shape_record, 17, arc.center_y)
        struct.pack_into('<i', shape_record, 21, arc.radius)
        struct.pack_into('<d', shape_record, 25, arc.start_angle)
        struct.pack_into('<d', shape_record, 33, arc.end_angle)
        struct.pack_into('<i', shape_record, 41, arc.width)
        record = bytearray([0x01])
        record.extend(struct.pack('<I', len(shape_record)))
        record.extend(shape_record)
        return bytes(record)

    def pack_fill(self, fill: Fill) -> bytes:
        shape_record = bytearray(37)
        shape_record[:13] = self._common_header(fill.layer)
        struct.pack_into('<i', shape_record, 13, fill.x1)
        struct.pack_into('<i', shape_record, 17, fill.y1)
        struct.pack_into('<i', shape_record, 21, fill.x2)
        struct.pack_into('<i', shape_record, 25, fill.y2)
        struct.pack_into('<d', shape_record, 29, fill.rotation)
        record = bytearray([0x06])
        record.extend(struct.pack('<I', len(shape_record)))
        record.extend(shape_record)
        return bytes(record)

    def pack_region(self, region: Region) -> bytes:
        body = bytearray()
        body.extend(self._common_header(region.layer))
        body.extend(struct.pack('<I', 0))
        body.append(0)
        body.extend(_write_cstring_param_block({}))
        body.extend(struct.pack('<I', len(region.points)))
        for x, y in region.points:
            body.extend(struct.pack('<d', float(x)))
            body.extend(struct.pack('<d', float(y)))

        record = bytearray([0x0B])
        record.extend(struct.pack('<I', len(body)))
        record.extend(body)
        return bytes(record)

    def pack_component_body(self, footprint: Footprint) -> bytes:
        model = getattr(footprint, 'model_3d', None)
        if not model or not model.step_path or not os.path.exists(model.step_path):
            return b''

        overall_height_mil = self._mm_to_mil(max(model.placement_z_mm + model.height_mm, 0.0))
        model_id = PcbLibWriter._model_guid(footprint, model)
        model_name = os.path.basename(model.step_path)
        body = bytearray()
        body.extend(self._common_header(57, flags=0x000C))
        body.extend(struct.pack('<I', 0))
        body.append(0)
        body.extend(self._write_body_param_block([
            ('V7_LAYER', 'MECHANICAL1'),
            ('NAME', ' '),
            ('KIND', '0'),
            ('SUBPOLYINDEX', '-1'),
            ('UNIONINDEX', '0'),
            ('ARCRESOLUTION', '0.5mil'),
            ('ISSHAPEBASED', 'FALSE'),
            ('CAVITYHEIGHT', '0mil'),
            ('STANDOFFHEIGHT', '0mil'),
            ('OVERALLHEIGHT', f'{overall_height_mil:.4f}mil'),
            ('BODYPROJECTION', '0'),
            ('ARCRESOLUTION', '0.5mil'),
            ('BODYCOLOR3D', '8421504'),
            ('BODYOPACITY3D', '1.000'),
            ('IDENTIFIER', self._identifier_bytes(model_name)),
            ('TEXTURE', ''),
            ('TEXTURECENTERX', '0mil'),
            ('TEXTURECENTERY', '0mil'),
            ('TEXTURESIZEX', '0mil'),
            ('TEXTURESIZEY', '0mil'),
            ('TEXTUREROTATION', ' 0.00000000000000E+0000'),
            ('MODELID', model_id),
            ('MODEL.CHECKSUM', '0'),
            ('MODEL.EMBED', 'TRUE'),
            ('MODEL.NAME', model_name),
            ('MODEL.2D.X', '0mil'),
            ('MODEL.2D.Y', '0mil'),
            ('MODEL.2D.ROTATION', '0.000'),
            ('MODEL.3D.ROTX', f'{model.recommended_rotation_x:.3f}'),
            ('MODEL.3D.ROTY', f'{model.recommended_rotation_y:.3f}'),
            ('MODEL.3D.ROTZ', f'{model.recommended_rotation_z:.3f}'),
            ('MODEL.3D.DZ', f'{self._raw_to_mil(int(round(model.altium_offset_z)))}mil'),
            ('MODEL.MODELTYPE', '1'),
            ('MODEL.MODELSOURCE', 'Undefined'),
        ]))

        outline = self._component_body_outline(footprint)
        body.extend(struct.pack('<I', len(outline)))
        for x, y in outline:
            body.extend(struct.pack('<d', float(x)))
            body.extend(struct.pack('<d', float(y)))

        record = bytearray([0x0C])
        record.extend(struct.pack('<I', len(body)))
        record.extend(body)
        return bytes(record)

    @staticmethod
    def _mm_to_mil(value_mm: float) -> float:
        return value_mm / 0.0254

    @staticmethod
    def _raw_to_mil(value: int) -> str:
        text = f'{value / 10000.0:.4f}'.rstrip('0').rstrip('.')
        return text or '0'

    @staticmethod
    def _component_body_outline(footprint: Footprint) -> list[tuple[float, float]]:
        bounds = PcbLibWriter._footprint_bounds(footprint)
        if not bounds:
            return []
        min_x, min_y, max_x, max_y = bounds
        return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]

    @staticmethod
    def _write_body_param_block(params) -> bytes:
        items = params.items() if isinstance(params, dict) else params
        text = '|'.join(f'{key}={value}' for key, value in items)
        data = text.encode('ascii', errors='replace') + b'\x00'
        return struct.pack('<I', len(data)) + data

    @staticmethod
    def _identifier_bytes(model_name: str) -> str:
        stem = os.path.splitext(model_name)[0]
        return ','.join(str(byte) for byte in stem.encode('ascii', errors='replace'))


class PcbLibWriter:
    ROOT_STORAGES = {'FileHeader', 'Library', 'FileVersionInfo', 'SectionKeys'}
    COMPONENT_STREAM_PREFIXES = (
        'Data',
        'Header',
        'Parameters',
        'WideStrings',
        'UniqueIdPrimitiveInformation/',
        'PrimitiveGuids/',
        'LayerToLayerMapping',
        'ExtendedPrimitiveInformation/',
    )

    def __init__(self):
        self.packer = RecordPacker()

    @staticmethod
    def _make_file_header() -> bytes:
        template = _get_file_header()
        if template:
            return template
        buf = bytearray()
        sig = b'PCB 6.0 Binary Library File'
        buf.extend(struct.pack('<i', len(sig)))
        buf.append(len(sig))
        buf.extend(sig)
        buf.extend(struct.pack('<d', 5.01))
        buf.extend(struct.pack('<h', 8))
        buf.append(0)
        uid = b'JLC2ADPY'
        buf.append(len(uid))
        buf.extend(uid)
        return bytes(buf)

    def _make_library_data(self, storage_names: List[str], filename: str) -> bytes:
        buf = bytearray()
        full_params = _get_library_params()
        if full_params:
            full_params = full_params.replace(
                'FILENAME=D:\\BrainCoWorkspace\\AltiumDesignerLibPkg-dream\\RC\\RC.$$$',
                f'FILENAME={filename}$$$'
            )
            full_params = re.sub(r'\|WEIGHT=\d+', f'|WEIGHT={len(storage_names)}', full_params)
            params_bytes = full_params.encode('ascii', errors='replace') + b'\x00'
            buf.extend(struct.pack('<I', len(params_bytes)))
            buf.extend(params_bytes)
        else:
            buf.extend(_write_cstring_param_block({
                'HEADER': 'PCB 6.0 Binary Library File',
                'WEIGHT': str(len(storage_names)),
            }))

        buf.extend(struct.pack('<I', len(storage_names)))
        for storage_name in storage_names:
            buf.extend(_write_string_block(storage_name))
        return bytes(buf)

    def _build_models_streams(
        self,
        footprints: List[Footprint],
        existing_models_data: bytes = b'',
        existing_model_payloads: List[bytes] = None,
    ) -> tuple[bytes, bytes, List[bytes]]:
        data_stream = bytearray(existing_models_data or b'')
        model_payloads = list(existing_model_payloads or [])

        for footprint in footprints:
            model = getattr(footprint, 'model_3d', None)
            if not model or not model.step_path or not os.path.exists(model.step_path):
                continue
            with open(model.step_path, 'rb') as file:
                step_data = file.read()
            payload = zlib.compress(step_data, level=0)
            model_payloads.append(payload)
            model_name = os.path.basename(model.step_path)
            model_id = self._model_guid(footprint, model)
            entry = (
                f'EMBED=TRUE|MODELSOURCE=Undefined|ID={model_id}|'
                f'ROTX={model.recommended_rotation_x:.3f}|ROTY={model.recommended_rotation_y:.3f}|'
                f'ROTZ={model.recommended_rotation_z:.3f}|DZ={int(round(model.altium_offset_z))}|'
                f'CHECKSUM=0|NAME={model_name}'
            ).encode('ascii', errors='replace') + b'\x00'
            data_stream.extend(struct.pack('<I', len(entry)))
            data_stream.extend(entry)

        header_stream = struct.pack('<I', len(model_payloads))
        return header_stream, bytes(data_stream), model_payloads

    @staticmethod
    def _model_guid(footprint: Footprint, model) -> str:
        seed = f'{footprint.name}|{getattr(model, "uuid", "")}|{os.path.basename(getattr(model, "step_path", ""))}'
        return '{' + str(uuid.uuid5(uuid.NAMESPACE_URL, seed)).upper() + '}'

    def _build_component_data(self, footprint: Footprint, storage_name: str) -> bytes:
        buf = bytearray()
        buf.extend(_write_string_block(storage_name))
        for pad in footprint.pads:
            buf.extend(self.packer.pack_pad(pad))
        for track in footprint.tracks:
            buf.extend(self.packer.pack_track(track))
        for arc in footprint.arcs:
            buf.extend(self.packer.pack_arc(arc))
        for fill in footprint.fills:
            buf.extend(self.packer.pack_fill(fill))
        for region in footprint.regions:
            buf.extend(self.packer.pack_region(region))
        body_record = self.packer.pack_component_body(footprint)
        if body_record:
            buf.extend(body_record)
        return bytes(buf)

    @staticmethod
    def _build_header(footprint: Footprint) -> bytes:
        body_count = 1 if getattr(footprint, 'model_3d', None) and footprint.model_3d.step_path else 0
        return struct.pack('<I', len(footprint.pads) + len(footprint.tracks) + len(footprint.arcs) + len(footprint.fills) + len(footprint.regions) + body_count)

    @staticmethod
    def _build_parameters(footprint: Footprint, storage_name: str) -> bytes:
        params = {
            'PATTERN': footprint.name,
            'HEIGHT': '0',
        }
        if getattr(footprint, 'package', ''):
            params['PACKAGE'] = footprint.package
        if getattr(footprint, 'value', ''):
            params['Value'] = footprint.value
        if getattr(footprint, 'manufacturer', ''):
            params['Manufacturer'] = footprint.manufacturer
        if getattr(footprint, 'manufacturer_part', ''):
            params['Manufacturer Part'] = footprint.manufacturer_part
        if getattr(footprint, 'supplier_part', ''):
            params['Supplier Part'] = footprint.supplier_part
        if getattr(footprint, 'supplier', ''):
            params['Supplier'] = footprint.supplier
        if getattr(footprint, 'datasheet', ''):
            params['Datasheet'] = footprint.datasheet
        if getattr(footprint, 'jlcpcb_part_class', ''):
            params['JLCPCB Part Class'] = footprint.jlcpcb_part_class
        if getattr(footprint, 'symbol_name', ''):
            params['Symbol'] = footprint.symbol_name
        if getattr(footprint, 'lcsc_part_name', ''):
            params['LCSC Part Name'] = footprint.lcsc_part_name
        if getattr(footprint, 'model_3d_name', ''):
            params['3D Model Name'] = footprint.model_3d_name
        if getattr(footprint, 'model_3d_title', ''):
            params['3D Model Title'] = footprint.model_3d_title
        if getattr(footprint, 'model_3d_uuid', ''):
            params['3D Model UUID'] = footprint.model_3d_uuid
        if getattr(footprint, 'model_3d_transform', ''):
            params['3D Model Transform'] = footprint.model_3d_transform
        if getattr(footprint, 'description', ''):
            params['DESCRIPTION'] = footprint.description
        return _write_cstring_param_block(params)

    @staticmethod
    def _build_wide_strings() -> bytes:
        return _write_cstring_param_block({})

    @staticmethod
    def _build_unique_id_header(footprint: Footprint) -> bytes:
        return PcbLibWriter._build_header(footprint)

    @staticmethod
    def _build_unique_id_data(footprint: Footprint) -> bytes:
        buf = bytearray()
        index = 0
        for _ in footprint.pads:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'Pad'))
            index += 1
        for _ in footprint.tracks:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'Track'))
            index += 1
        for _ in footprint.arcs:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'Arc'))
            index += 1
        for _ in footprint.fills:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'Region'))
            index += 1
        for _ in footprint.regions:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'Region'))
            index += 1
        if getattr(footprint, 'model_3d', None) and footprint.model_3d.step_path:
            buf.extend(PcbLibWriter._primitive_info_record(index, 'ComponentBody'))
        return bytes(buf)

    @staticmethod
    def _primitive_info_record(index: int, object_id: str) -> bytes:
        params = {'PRIMITIVEOBJECTID': object_id}
        if index > 0:
            params = {'PRIMITIVEINDEX': str(index), 'PRIMITIVEOBJECTID': object_id}
        return _write_cstring_param_block(params)

    @staticmethod
    def _footprint_bounds(footprint: Footprint):
        xs = []
        ys = []
        for pad in footprint.pads:
            xs.extend([pad.x - pad.size_x / 2.0, pad.x + pad.size_x / 2.0])
            ys.extend([pad.y - pad.size_y / 2.0, pad.y + pad.size_y / 2.0])
        for track in footprint.tracks:
            half = track.width / 2.0
            xs.extend([track.x1 - half, track.x1 + half, track.x2 - half, track.x2 + half])
            ys.extend([track.y1 - half, track.y1 + half, track.y2 - half, track.y2 + half])
        for arc in footprint.arcs:
            r = arc.radius + arc.width / 2.0
            xs.extend([arc.center_x - r, arc.center_x + r])
            ys.extend([arc.center_y - r, arc.center_y + r])
        for fill in footprint.fills:
            xs.extend([fill.x1, fill.x2])
            ys.extend([fill.y1, fill.y2])
        for region in footprint.regions:
            for x, y in region.points:
                xs.append(x)
                ys.append(y)
        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def _build_cfb(
        self,
        footprints: List[Footprint],
        storage_names: List[str],
        filename: str = '',
        existing_raw: dict = None,
        existing_models_data: bytes = b'',
        existing_model_payloads: List[bytes] = None,
        existing_library_streams: dict = None,
    ) -> CfbWriter:
        cfb = CfbWriter()
        cfb.add_stream('FileHeader', self._make_file_header())

        all_storage_names = list((existing_raw or {}).keys()) + storage_names
        cfb.add_stream('Library/Header', struct.pack('<I', 1))
        cfb.add_stream('Library/Data', self._make_library_data(all_storage_names, filename))
        models_header, models_data, model_payloads = self._build_models_streams(
            footprints,
            existing_models_data=existing_models_data,
            existing_model_payloads=existing_model_payloads,
        )
        cfb.add_stream('Library/Models/Header', models_header)
        if model_payloads:
            cfb.add_stream('Library/Models/Data', models_data)
            for index, payload in enumerate(model_payloads):
                cfb.add_stream(f'Library/Models/{index}', payload)
        else:
            cfb.add_stream('Library/Models/Data', b'')
        library_streams = existing_library_streams or {}
        cfb.add_stream('Library/Textures/Header', library_streams.get('Textures/Header', struct.pack('<I', 0)))
        cfb.add_stream('Library/Textures/Data', library_streams.get('Textures/Data', b''))
        cfb.add_stream('Library/ModelsNoEmbed/Header', library_streams.get('ModelsNoEmbed/Header', struct.pack('<I', 0)))
        cfb.add_stream('Library/ModelsNoEmbed/Data', library_streams.get('ModelsNoEmbed/Data', b''))

        if existing_raw:
            for storage_name, streams in existing_raw.items():
                for stream_name, data in streams.items():
                    cfb.add_stream(f'{storage_name}/{stream_name}', data)

        for footprint, storage_name in zip(footprints, storage_names):
            cfb.add_stream(f'{storage_name}/Header', self._build_header(footprint))
            cfb.add_stream(f'{storage_name}/Parameters', self._build_parameters(footprint, storage_name))
            cfb.add_stream(f'{storage_name}/WideStrings', self._build_wide_strings())
            cfb.add_stream(f'{storage_name}/Data', self._build_component_data(footprint, storage_name))
            cfb.add_stream(f'{storage_name}/UniqueIdPrimitiveInformation/Header', self._build_unique_id_header(footprint))
            cfb.add_stream(f'{storage_name}/UniqueIdPrimitiveInformation/Data', self._build_unique_id_data(footprint))
        return cfb

    @staticmethod
    def _safe_name(name: str) -> str:
        return _safe_storage_name(name)

    def write(self, filename: str, footprints: List[Footprint]):
        storage_names = [self._safe_name(footprint.name) for footprint in footprints]
        self._build_cfb(footprints, storage_names, filename).save(filename)

    def append(self, filename: str, footprints: List[Footprint]):
        import olefile

        existing_raw = {}
        existing_names = set()
        existing_part_ids = set()
        existing_models_data = b''
        existing_model_payloads = []
        existing_library_streams = {}

        if os.path.exists(filename):
            ole = olefile.OleFileIO(filename)
            for entry in ole.listdir(storages=True):
                if len(entry) == 1 and entry[0] not in self.ROOT_STORAGES:
                    existing_names.add(entry[0])
            for name in existing_names:
                existing_raw[name] = {}
                prefix = f'{name}/'
                for entry in ole.listdir(streams=True):
                    path = '/'.join(entry)
                    if not path.startswith(prefix):
                        continue
                    stream_name = path[len(prefix):]
                    if self._should_preserve_component_stream(stream_name):
                        existing_raw[name][stream_name] = ole.openstream(path).read()
                existing_part_ids.update(self._extract_part_ids(existing_raw[name].get('Parameters', b'')))

            try:
                existing_models_data = ole.openstream('Library/Models/Data').read()
            except Exception:
                existing_models_data = b''
            model_count = self._read_existing_model_count(ole)
            for index in range(model_count):
                try:
                    existing_model_payloads.append(ole.openstream(f'Library/Models/{index}').read())
                except Exception:
                    break
            for stream_name in ('Textures/Header', 'Textures/Data', 'ModelsNoEmbed/Header', 'ModelsNoEmbed/Data'):
                try:
                    existing_library_streams[stream_name] = ole.openstream(f'Library/{stream_name}').read()
                except Exception:
                    pass
            ole.close()

        new_footprints = []
        new_storage_names = []
        for footprint in footprints:
            storage_name = self._safe_name(footprint.name)
            part_id = self._normalized_part_id(getattr(footprint, 'supplier_part', ''))
            if part_id and part_id in existing_part_ids:
                print(f'  Skipping existing part: {part_id}')
                continue
            if storage_name in existing_names:
                print(f'  Skipping existing: {storage_name}')
                continue
            new_footprints.append(footprint)
            new_storage_names.append(storage_name)

        self._build_cfb(
            new_footprints,
            new_storage_names,
            filename,
            existing_raw,
            existing_models_data=existing_models_data,
            existing_model_payloads=existing_model_payloads,
            existing_library_streams=existing_library_streams,
        ).save(filename)

    @classmethod
    def _should_preserve_component_stream(cls, stream_name: str) -> bool:
        return any(stream_name == prefix or stream_name.startswith(prefix) for prefix in cls.COMPONENT_STREAM_PREFIXES)

    @staticmethod
    def _read_existing_model_count(ole) -> int:
        try:
            data = ole.openstream('Library/Models/Header').read(4)
            if len(data) == 4:
                return struct.unpack('<I', data)[0]
        except Exception:
            pass
        count = 0
        while True:
            try:
                ole.openstream(f'Library/Models/{count}').close()
            except Exception:
                return count
            count += 1

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
        marker = f'|{key}='
        start = text.find(marker)
        if start < 0:
            return ''
        start += len(marker)
        end = text.find('|', start)
        if end < 0:
            end = len(text)
        return text[start:end].strip('\x00 ').upper()

    @staticmethod
    def _normalized_part_id(value: str) -> str:
        value = (value or '').strip().upper()
        match = re.search(r'\bC\d+\b', value)
        return match.group(0) if match else ''


__all__ = ['RecordPacker', 'PcbLibWriter']
