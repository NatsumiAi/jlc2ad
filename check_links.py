import argparse
import olefile


def collect_pcblib_names(pcblib_path: str) -> set[str]:
    ole = olefile.OleFileIO(pcblib_path)
    try:
        names = {
            e[0]
            for e in ole.listdir(storages=True)
            if len(e) == 1 and e[0] not in ('FileHeader', 'Library', 'SectionKeys', 'FileVersionInfo')
        }
        return names
    finally:
        ole.close()


def collect_sch_models(schlib_path: str) -> list[tuple[str, str]]:
    ole = olefile.OleFileIO(schlib_path)
    pairs: list[tuple[str, str]] = []
    try:
        for entry in ole.listdir(storages=True):
            if len(entry) == 2 and entry[1] == 'Data':
                sym = entry[0]
                data = ole.openstream(entry).read()
                key = b'ModelDatafileEntity0='
                idx = data.find(key)
                if idx < 0:
                    continue
                tail = data[idx + len(key):]
                end = tail.find(b'|')
                if end < 0:
                    continue
                model_entity = tail[:end].decode('ascii', errors='replace')
                pairs.append((sym, model_entity))
        return pairs
    finally:
        ole.close()


def main() -> int:
    ap = argparse.ArgumentParser(description='Check SchLib->PcbLib model link consistency')
    ap.add_argument('--schlib', default='test_big.SchLib')
    ap.add_argument('--pcblib', default='test_big.PcbLib')
    args = ap.parse_args()

    pcb_names = collect_pcblib_names(args.pcblib)
    models = collect_sch_models(args.schlib)

    missing = [(sym, model) for sym, model in models if model not in pcb_names]

    print(f'Sch models: {len(models)}')
    print(f'Pcb footprints: {len(pcb_names)}')
    print(f'Missing links: {len(missing)}')

    for sym, model in missing:
        print(f'  {sym} -> {model} (NOT FOUND)')

    if not missing:
        print('All SchLib model links resolve to PcbLib footprints.')
        return 0
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
