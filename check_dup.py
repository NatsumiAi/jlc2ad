import olefile
g = olefile.OleFileIO('my_lib.PcbLib')
counts = {}
for e in g.listdir():
    if len(e) == 2 and e[1] == 'Data':
        name = e[0]
        counts[name] = counts.get(name, 0) + 1

for name, count in sorted(counts.items()):
    print(name, ':', count)
g.close()
