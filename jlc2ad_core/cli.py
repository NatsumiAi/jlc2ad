import argparse
import sys

from .build import build_libraries

def main():
    ap = argparse.ArgumentParser(
        description='LCSC -> Altium Designer SchLib + PcbLib + LibPkg',
        epilog='Example: python jlc2ad.py C15850 C25804 -o my_lib')
    ap.add_argument('parts', nargs='+', help='LCSC part number (e.g. C15850)')
    ap.add_argument('-o', '--output', default='output',
                    help='Output base name, e.g. "my_lib" -> my_lib.SchLib + my_lib.PcbLib + my_lib.LibPkg')
    args = ap.parse_args()

    try:
        result = build_libraries(args.parts, args.output, log=print)
    except ValueError as exc:
        print(f"{exc}. Exiting.")
        sys.exit(1)

    print(f"\nDone! Files created:")
    print(f"  {result.pcblib_path}")
    if result.symbols:
        print(f"  {result.schlib_path}")
    print(f"  {result.libpkg_path}")
    print(
        f"\nTo create IntLib: Open {result.libpkg_path} in AD24 -> Project -> Compile Integrated Library"
    )


if __name__ == '__main__':
    main()
