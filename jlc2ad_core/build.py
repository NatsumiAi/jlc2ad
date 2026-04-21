import os
from dataclasses import dataclass
from typing import Callable, List, Optional

from .easyeda_api import EasyEDAClient
from .footprint_parser import FootprintParser
from .libpkg_writer import LibPkgWriter
from .pcb_writer import PcbLibWriter
from .sch_writer import SchLibWriter
from .schematic_parser import SchematicParser
from .types import Footprint, SchSymbol


LogFn = Callable[[str], None]
ProgressFn = Callable[[float], None]


@dataclass
class BuildResult:
    base_name: str
    pcblib_path: str
    schlib_path: str
    libpkg_path: str
    footprints: List[Footprint]
    symbols: List[SchSymbol]


def normalize_output_base(output_name: str) -> str:
    base = output_name.strip()
    for ext in ('.PcbLib', '.SchLib', '.LibPkg', '.IntLib'):
        if base.lower().endswith(ext.lower()):
            return base[:-len(ext)]
    return base


def build_libraries(
    parts: List[str],
    output_name: str,
    log: Optional[LogFn] = None,
    progress: Optional[ProgressFn] = None,
) -> BuildResult:
    client = EasyEDAClient()
    fp_parser = FootprintParser()
    sch_parser = SchematicParser()
    pcb_writer = PcbLibWriter()
    sch_writer = SchLibWriter()

    base = normalize_output_base(output_name)
    pcblib_path = base + '.PcbLib'
    schlib_path = base + '.SchLib'
    libpkg_path = base + '.LibPkg'

    footprints: List[Footprint] = []
    symbols: List[SchSymbol] = []
    total = len(parts)

    def emit(message: str):
        if log:
            log(message)

    def update_progress(value: float):
        if progress:
            progress(value)

    for index, pid in enumerate(parts):
        emit(f"Fetching {pid} ...")
        try:
            data = client.fetch(pid)
            emit(f"  Component: {data['title']} ({data['package_name']})")

            fp = fp_parser.parse(data)
            full_desc = f"{data['description']} [{pid}]" if data['description'] else pid
            fp.description = full_desc
            fp.package = data.get('package', data.get('package_name', ''))
            fp.value = data.get('value', '')
            fp.manufacturer = data.get('manufacturer', '')
            fp.manufacturer_part = data.get('manufacturer_part', '')
            fp.supplier_part = data.get('supplier_part', pid)
            fp.supplier = data.get('supplier', 'LCSC')
            fp.datasheet = data.get('datasheet', '')
            fp.jlcpcb_part_class = data.get('attributes', {}).get('JLCPCB Part Class', '')
            fp.symbol_name = data.get('attributes', {}).get('Symbol', '')
            fp.lcsc_part_name = data.get('attributes', {}).get('LCSC Part Name', '')
            fp.model_3d_name = data.get('model_3d', {}).get('3D Model Name', '')
            fp.model_3d_title = data.get('model_3d', {}).get('3D Model Title', '')
            fp.model_3d_uuid = data.get('model_3d', {}).get('3D Model UUID', '') or data.get('model_3d', {}).get('uuid', '')
            fp.model_3d_transform = data.get('model_3d', {}).get('transform_raw', '')
            emit(f"  PCB: {len(fp.pads)} pads, {len(fp.tracks)} tracks, {len(fp.arcs)} arcs")
            footprints.append(fp)

            sym = sch_parser.parse(data)
            if sym:
                sym.name = data.get('title', fp.name)
                sym.description = full_desc
                sym.package = data.get('package', data.get('package_name', sym.package))
                sym.manufacturer = data.get('manufacturer', sym.manufacturer)
                sym.manufacturer_part = data.get('manufacturer_part', data.get('title', sym.name))
                sym.value = data.get('value', sym.value)
                sym.supplier_part = data.get('supplier_part', data.get('lcsc_id', sym.supplier_part))
                sym.supplier = data.get('supplier', sym.supplier)
                sym.datasheet = data.get('datasheet', '')
                sym.jlcpcb_part_class = data.get('attributes', {}).get('JLCPCB Part Class', '')
                sym.symbol_name = data.get('attributes', {}).get('Symbol', sym.name)
                sym.lcsc_part_name = data.get('attributes', {}).get('LCSC Part Name', data.get('title', sym.name))
                sym.model_3d_name = data.get('model_3d', {}).get('3D Model Name', '')
                sym.model_3d_title = data.get('model_3d', {}).get('3D Model Title', '')
                sym.model_3d_uuid = data.get('model_3d', {}).get('3D Model UUID', '') or data.get('model_3d', {}).get('uuid', '')
                sym.model_3d_transform = data.get('model_3d', {}).get('transform_raw', '')
                emit(f"  SCH: {len(sym.pins)} pins, {len(sym.lines)} lines, {len(sym.rects)} rects")
                symbols.append(sym)
            else:
                emit("  SCH: no schematic data, skipping symbol")
        except Exception as exc:
            emit(f"  Error: {exc}")
            continue

        if total:
            update_progress((index + 1) / total * 0.7)

    if not footprints:
        raise ValueError("No components fetched")

    if os.path.exists(pcblib_path):
        emit(f"\n{pcblib_path} exists, appending...")
        pcb_writer.append(pcblib_path, footprints)
    else:
        emit(f"\nCreating {pcblib_path} ...")
        pcb_writer.write(pcblib_path, footprints)
    emit(f"  {len(footprints)} footprint(s)")
    update_progress(0.8)

    if symbols:
        if os.path.exists(schlib_path):
            emit(f"\n{schlib_path} exists, appending...")
            sch_writer.append(schlib_path, symbols)
        else:
            emit(f"\nCreating {schlib_path} ...")
            sch_writer.write(schlib_path, symbols)
        emit(f"  {len(symbols)} symbol(s)")

    LibPkgWriter.write(libpkg_path, os.path.basename(schlib_path), os.path.basename(pcblib_path))
    emit(f"\nCreating {libpkg_path} ...")
    update_progress(1.0)

    return BuildResult(
        base_name=base,
        pcblib_path=pcblib_path,
        schlib_path=schlib_path,
        libpkg_path=libpkg_path,
        footprints=footprints,
        symbols=symbols,
    )


__all__ = ["BuildResult", "build_libraries", "normalize_output_base"]
