import olefile
rc = olefile.OleFileIO('RC.SchLib')
data = rc.openstream('Resistor_SMD/Data').read()

# Find all Model related fields
parts = data.split(b'|')
for p in parts:
    if b'Model' in p or b'Datafile' in p or b'PCBLIB' in p:
        print(p)
rc.close()
