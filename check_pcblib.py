import olefile
g = olefile.OleFileIO('my_lib.PcbLib')
for e in g.listdir():
    if len(e) == 2 and e[1] == 'Parameters':
        print(e[0])
g.close()
