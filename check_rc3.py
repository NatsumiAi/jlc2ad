import olefile
rc = olefile.OleFileIO('RC.PcbLib')
# Get all footprint names
for e in rc.listdir():
    if len(e) == 2 and e[1] == 'Data':
        print(e[0])
rc.close()
