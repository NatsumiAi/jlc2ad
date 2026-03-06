import olefile
g = olefile.OleFileIO('my_lib.SchLib')
for e in g.listdir():
    if len(e) == 2 and e[1] == 'Data':
        data = g.openstream(e).read()
        if b'ModelName=' in data:
            idx = data.find(b'ModelName=')
            name = data[idx:idx+60]
            print(e[0], ':', name)
g.close()
