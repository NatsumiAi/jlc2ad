import olefile
rc = olefile.OleFileIO('RC.SchLib')
data = rc.openstream('Resistor_SMD/Data').read()

# Search for ModelDatafileName
idx = data.find(b'ModelDatafileName')
print('ModelDatafileName found:', idx >= 0)

# Also check what fields we have
parts = data.split(b'|')
for p in parts:
    if b'ModelDatafile' in p:
        print(p)

rc.close()
