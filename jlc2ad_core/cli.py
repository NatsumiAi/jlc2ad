import argparse
import os
import sys

from .parsers import EasyEDAClient, FootprintParser, SchematicParser
from .writers import LibPkgWriter, PcbLibWriter, SchLibWriter

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
