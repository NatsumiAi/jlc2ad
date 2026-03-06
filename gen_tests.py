#!/usr/bin/env python3
"""Generate diagnostic PcbLib test files."""
import olefile, struct, os, sys, re
sys.path.insert(0, '.')
from jlc2ad import CfbWriter, _write_string_block, _write_cstring_param_block

rc = olefile.OleFileIO('RC.PcbLib')

# Parse RC's Library/Data to get component names
ld = rc.openstream('Library/Data').read()
off = 0
param_len = struct.unpack_from('<I', ld, off)[0]; off += 4 + param_len
comp_count = struct.unpack_from('<I', ld, off)[0]; off += 4
comp_names = []
for i in range(comp_count):
    sb_len = struct.unpack_from('<I', ld, off)[0]; off += 4
    name_len = ld[off]; off += 1
    name = ld[off:off+name_len].decode('ascii', errors='replace')
    off += sb_len - 1
    comp_names.append(name)

# ===== TEST A: RC everything, but Library/Data uses our MINIMAL format =====
print("Creating test_a.PcbLib (RC streams + minimal Library/Data)...")
cfb_a = CfbWriter()
all_streams = {}
for entry in rc.listdir(streams=True, storages=False):
    path = '/'.join(entry)
    data = rc.openstream(entry).read()
    all_streams[path] = data

min_ld = bytearray()
min_ld.extend(_write_cstring_param_block({
    'HEADER': 'PCB 6.0 Binary Library File',
    'WEIGHT': str(comp_count),
}))
min_ld.extend(struct.pack('<I', comp_count))
for name in comp_names:
    min_ld.extend(_write_string_block(name))
all_streams['Library/Data'] = bytes(min_ld)

for path, data in all_streams.items():
    cfb_a.add_stream(path, data)
cfb_a.save('test_a.PcbLib')
print(f"  OK - Library/Data: {len(min_ld)} -> was {len(ld)}")

# ===== TEST B: RC's 1 component with full Library params =====
print("Creating test_b.PcbLib (RC 1 comp + full Library params)...")
cfb_b = CfbWriter()
first_comp = comp_names[0]

rc_params_raw = ld[4:4+param_len-1].decode('ascii', errors='replace')
rc_params_fixed = re.sub(r'\|WEIGHT=\d+', '|WEIGHT=1', rc_params_raw)
params_bytes = rc_params_fixed.encode('ascii') + b'\x00'
full_ld = bytearray()
full_ld.extend(struct.pack('<I', len(params_bytes)))
full_ld.extend(params_bytes)
full_ld.extend(struct.pack('<I', 1))
full_ld.extend(_write_string_block(first_comp))

cfb_b.add_stream('FileHeader', rc.openstream('FileHeader').read())
cfb_b.add_stream('Library/Header', struct.pack('<I', 1))
cfb_b.add_stream('Library/Data', bytes(full_ld))
cfb_b.add_stream('Library/Models/Header', rc.openstream('Library/Models/Header').read())
cfb_b.add_stream('Library/Models/Data', rc.openstream('Library/Models/Data').read())
for entry in rc.listdir(streams=True, storages=False):
    path = '/'.join(entry)
    if path.startswith(first_comp + '/'):
        cfb_b.add_stream(path, rc.openstream(entry).read())
cfb_b.save('test_b.PcbLib')
print(f"  OK - comp: {first_comp}")

# ===== TEST C: EMPTY PcbLib (0 components) =====
print("Creating test_c.PcbLib (EMPTY, 0 components)...")
cfb_c = CfbWriter()
cfb_c.add_stream('FileHeader', rc.openstream('FileHeader').read())
cfb_c.add_stream('Library/Header', struct.pack('<I', 1))
empty_ld = bytearray()
empty_ld.extend(_write_cstring_param_block({
    'HEADER': 'PCB 6.0 Binary Library File',
    'WEIGHT': '0',
}))
empty_ld.extend(struct.pack('<I', 0))
cfb_c.add_stream('Library/Data', bytes(empty_ld))
cfb_c.add_stream('Library/Models/Header', struct.pack('<I', 0))
cfb_c.add_stream('Library/Models/Data', b'')
cfb_c.save('test_c.PcbLib')
print("  OK")

# ===== TEST D: Our C0805 component + RC-style full Library params =====
print("Creating test_d.PcbLib (our C0805 + full Library params from RC)...")
our = olefile.OleFileIO('test_min.PcbLib')
our_comp_data = our.openstream('C0805/Data').read()
our_comp_hdr = our.openstream('C0805/Header').read()
our_comp_params = our.openstream('C0805/Parameters').read()
our_comp_ws = our.openstream('C0805/WideStrings').read()
our.close()

cfb_d = CfbWriter()
cfb_d.add_stream('FileHeader', rc.openstream('FileHeader').read())
cfb_d.add_stream('Library/Header', struct.pack('<I', 1))

# Use RC's full params but WEIGHT=1 and 1 component
full_ld2 = bytearray()
full_ld2.extend(struct.pack('<I', len(params_bytes)))
full_ld2.extend(params_bytes)  # reuse from test_b (WEIGHT=1)
full_ld2.extend(struct.pack('<I', 1))
full_ld2.extend(_write_string_block('C0805'))
cfb_d.add_stream('Library/Data', bytes(full_ld2))
cfb_d.add_stream('Library/Models/Header', struct.pack('<I', 0))
cfb_d.add_stream('Library/Models/Data', b'')
cfb_d.add_stream('C0805/Data', our_comp_data)
cfb_d.add_stream('C0805/Header', our_comp_hdr)
cfb_d.add_stream('C0805/Parameters', our_comp_params)
cfb_d.add_stream('C0805/WideStrings', our_comp_ws)
cfb_d.save('test_d.PcbLib')
print(f"  OK - Library/Data: {len(full_ld2)} bytes")

# ===== TEST E: Our C0805 component + minimal Library + RC FileHeader =====
print("Creating test_e.PcbLib (our C0805 + minimal Library + RC FileHeader)...")
cfb_e = CfbWriter()
cfb_e.add_stream('FileHeader', rc.openstream('FileHeader').read())
cfb_e.add_stream('Library/Header', struct.pack('<I', 1))
min_ld2 = bytearray()
min_ld2.extend(_write_cstring_param_block({
    'HEADER': 'PCB 6.0 Binary Library File',
    'WEIGHT': '1',
}))
min_ld2.extend(struct.pack('<I', 1))
min_ld2.extend(_write_string_block('C0805'))
cfb_e.add_stream('Library/Data', bytes(min_ld2))
cfb_e.add_stream('Library/Models/Header', struct.pack('<I', 0))
cfb_e.add_stream('Library/Models/Data', b'')
cfb_e.add_stream('C0805/Data', our_comp_data)
cfb_e.add_stream('C0805/Header', our_comp_hdr)
cfb_e.add_stream('C0805/Parameters', our_comp_params)
cfb_e.add_stream('C0805/WideStrings', our_comp_ws)
cfb_e.save('test_e.PcbLib')
print("  OK")

rc.close()
print("\n=== Test in AD24: ===")
print("test_a: RC + minimal Library/Data -> tests if rich params needed")
print("test_b: RC 1-comp + full params -> tests single-comp w/ RC data")
print("test_c: EMPTY library -> tests if 0 components works")
print("test_d: Our data + full params + RC header -> tests our component data")
print("test_e: Our data + minimal params + RC header -> tests minimal format")
