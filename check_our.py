import olefile
g = olefile.OleFileIO('my_lib.SchLib')
for e in g.listdir():
    if len(e) == 2 and e[1] == 'Data':
        data = g.openstream(e).read()
        parts = data.split(b'|')
        for p in parts:
            if b'ModelDatafile' in p:
                print(e[0], ':', p)
g.close()
