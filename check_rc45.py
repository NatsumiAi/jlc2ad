import olefile

# Check RC library structure
rc = olefile.OleFileIO('RC.SchLib')
data = rc.openstream('Resistor_SMD/Data').read()

# Find RECORD=45 section
idx = data.find(b'RECORD=45|')
if idx >= 0:
    segment = data[idx:idx+300]
    print('RC RECORD=45 section:')
    print(segment)
    print()

# Also check our library
g = olefile.OleFileIO('my_lib.SchLib')
data = g.openstream('CL21A106KAYNNNE/Data').read()
idx = data.find(b'RECORD=45|')
if idx >= 0:
    segment = data[idx:idx+300]
    print('Our RECORD=45 section:')
    print(segment)
g.close()
