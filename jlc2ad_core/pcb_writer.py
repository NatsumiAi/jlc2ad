import os
import re
import struct
from typing import List

from .cfb_writer import CfbWriter
from .types import PCB_FLAGS_UNLOCKED, Arc, Fill, Footprint, Pad, Track
from .writer_common import _get_file_header, _get_library_params, _safe_storage_name, _write_cstring_param_block, _write_string_block


class RecordPacker:
    def _common_header(self, layer: int) -> bytearray:
        header = bytearray(13)
        header[0] = layer & 0xFF
        struct.pack_into('<H', header, 1, PCB_FLAGS_UNLOCKED)
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


class PcbLibWriter:
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
        return bytes(buf)

    @staticmethod
    def _build_header(footprint: Footprint) -> bytes:
        return struct.pack('<I', len(footprint.pads) + len(footprint.tracks) + len(footprint.arcs) + len(footprint.fills))

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

    def _build_cfb(self, footprints: List[Footprint], storage_names: List[str], filename: str = '', existing_raw: dict = None) -> CfbWriter:
        cfb = CfbWriter()
        cfb.add_stream('FileHeader', self._make_file_header())

        all_storage_names = list((existing_raw or {}).keys()) + storage_names
        cfb.add_stream('Library/Header', struct.pack('<I', 1))
        cfb.add_stream('Library/Data', self._make_library_data(all_storage_names, filename))
        cfb.add_stream('Library/Models/Header', struct.pack('<I', 0))
        cfb.add_stream('Library/Models/Data', b'')

        if existing_raw:
            for storage_name, streams in existing_raw.items():
                for stream_name, data in streams.items():
                    cfb.add_stream(f'{storage_name}/{stream_name}', data)

        for footprint, storage_name in zip(footprints, storage_names):
            cfb.add_stream(f'{storage_name}/Header', self._build_header(footprint))
            cfb.add_stream(f'{storage_name}/Parameters', self._build_parameters(footprint, storage_name))
            cfb.add_stream(f'{storage_name}/WideStrings', self._build_wide_strings())
            cfb.add_stream(f'{storage_name}/Data', self._build_component_data(footprint, storage_name))
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

        if os.path.exists(filename):
            ole = olefile.OleFileIO(filename)
            for entry in ole.listdir(storages=True):
                if len(entry) == 1 and entry[0] not in ('FileHeader', 'Library', 'FileVersionInfo', 'SectionKeys'):
                    existing_names.add(entry[0])
            for name in existing_names:
                existing_raw[name] = {}
                for stream_name in ('Data', 'Header', 'Parameters', 'WideStrings'):
                    try:
                        existing_raw[name][stream_name] = ole.openstream(f'{name}/{stream_name}').read()
                    except Exception:
                        pass
            ole.close()

        new_footprints = []
        new_storage_names = []
        for footprint in footprints:
            storage_name = self._safe_name(footprint.name)
            if storage_name in existing_names:
                print(f'  Skipping existing: {storage_name}')
                continue
            new_footprints.append(footprint)
            new_storage_names.append(storage_name)

        self._build_cfb(new_footprints, new_storage_names, filename, existing_raw).save(filename)


__all__ = ['RecordPacker', 'PcbLibWriter']
