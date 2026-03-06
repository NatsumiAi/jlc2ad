import olefile
rc = olefile.OleFileIO('RC.SchLib')
data = rc.openstream('Resistor_SMD/Data').read()
idx = data.find(b'ModelDatafileName')
if idx >= 0:
    print(data[idx:idx+50])
rc.close()
