import argparse
import subprocess
import sys


PARTS = [
    'C15850', 'C8291', 'C9652', 'C2235', 'C1161', 'C185260',
    'C100046', 'C100047', 'C100048', 'C100049', 'C100050',
    'C8357', 'C8560', 'C5139', 'C5140', 'C2990', 'C3020',
    'C3108', 'C3350', 'C43314', 'C43317', 'C46677', 'C46670',
]


def main() -> int:
    ap = argparse.ArgumentParser(description='Generate a large regression test library')
    ap.add_argument('-o', '--output', default='test_big', help='output basename')
    args = ap.parse_args()

    cmd = [sys.executable, 'jlc2ad.py', *PARTS, '-o', args.output]
    print('Running:', ' '.join(cmd))
    return subprocess.call(cmd)


if __name__ == '__main__':
    raise SystemExit(main())
