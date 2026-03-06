import olefile

# Check our generated library
g = olefile.OleFileIO('my_lib.SchLib')
for e in g.listdir():
    if len(e) == 2 and e[1] == 'Data':
        data = g.openstream(e).read()
        # Find the full Model section
        idx = data.find(b'ModelName=')
        if idx >= 0:
            segment = data[idx:idx+200]
            print(f'{e[0]}:')
            print(f'  {segment}')
            print()
g.close()
