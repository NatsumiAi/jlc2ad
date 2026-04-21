import os


class CfbWriter:
    """OLE/CFB 文件写入器 - 使用 Windows 原生 OLE32 API (通过 ctypes)"""

    STGM_DIRECT = 0x00000000
    STGM_READWRITE = 0x00000002
    STGM_SHARE_EXCLUSIVE = 0x00000010
    STGM_CREATE = 0x00001000
    STGM_WRITE = 0x00000001

    def __init__(self):
        self._streams = {}

    def add_stream(self, path: str, data: bytes):
        self._streams[path.replace('\\', '/')] = data

    def save(self, filename: str):
        import ctypes
        from ctypes import byref, c_ulong, c_void_p

        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        root_stg = c_void_p()
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE | self.STGM_DIRECT
        hr = ole32.StgCreateDocfile(
            ctypes.c_wchar_p(os.path.abspath(filename)),
            c_ulong(mode), c_ulong(0), byref(root_stg))
        if hr != 0:
            raise OSError(f"StgCreateDocfile failed: 0x{hr & 0xFFFFFFFF:08X}")

        try:
            storage_cache = {'': root_stg}
            for path, data in self._streams.items():
                parts = path.split('/')
                for i in range(len(parts) - 1):
                    storage_path = '/'.join(parts[:i + 1])
                    if storage_path not in storage_cache:
                        parent_path = '/'.join(parts[:i]) if i > 0 else ''
                        parent_stg = storage_cache[parent_path]
                        child_stg = c_void_p()
                        hr = self._create_storage(parent_stg, parts[i], child_stg)
                        if hr != 0:
                            raise OSError(f"CreateStorage '{parts[i]}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                        storage_cache[storage_path] = child_stg

                parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''
                parent_stg = storage_cache[parent_path]
                stream_name = parts[-1]
                stm = c_void_p()
                hr = self._create_stream(parent_stg, stream_name, stm)
                if hr != 0:
                    raise OSError(f"CreateStream '{stream_name}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                if data:
                    written = c_ulong(0)
                    buf = (ctypes.c_byte * len(data)).from_buffer_copy(data)
                    hr = self._stream_write(stm, buf, len(data), written)
                    if hr != 0:
                        raise OSError(f"Write to '{path}' failed: 0x{hr & 0xFFFFFFFF:08X}")
                self._release(stm)

            for storage_path in reversed(list(storage_cache.keys())):
                self._commit(storage_cache[storage_path])
            for storage_path in reversed(list(storage_cache.keys())):
                if storage_path:
                    self._release(storage_cache[storage_path])
        finally:
            self._release(root_stg)
            ole32.CoUninitialize()

    @staticmethod
    def _get_vtable(obj):
        import ctypes
        return ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents

    def _create_storage(self, parent_stg, name, out_stg):
        import ctypes
        from ctypes import byref, c_ulong, c_void_p

        vt = self._get_vtable(parent_stg)
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_wchar_p, c_ulong, c_ulong, c_ulong, ctypes.POINTER(c_void_p))
        func = func_type(vt[5])
        return func(parent_stg, name, mode, 0, 0, byref(out_stg))

    def _create_stream(self, parent_stg, name, out_stm):
        import ctypes
        from ctypes import byref, c_ulong, c_void_p

        vt = self._get_vtable(parent_stg)
        mode = self.STGM_CREATE | self.STGM_READWRITE | self.STGM_SHARE_EXCLUSIVE
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_wchar_p, c_ulong, c_ulong, c_ulong, ctypes.POINTER(c_void_p))
        func = func_type(vt[3])
        return func(parent_stg, name, mode, 0, 0, byref(out_stm))

    def _commit(self, stg):
        import ctypes
        from ctypes import c_ulong, c_void_p

        vt = self._get_vtable(stg)
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, c_ulong)
        func = func_type(vt[9])
        return func(stg, 0)

    def _stream_write(self, stm, buf, cb, written):
        import ctypes
        from ctypes import byref, c_ulong, c_void_p

        vt = self._get_vtable(stm)
        func_type = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.c_void_p, c_ulong, ctypes.POINTER(c_ulong))
        func = func_type(vt[4])
        return func(stm, buf, cb, byref(written))

    @staticmethod
    def _release(obj):
        import ctypes
        from ctypes import c_void_p

        if obj and obj.value:
            vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
            func_type = ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)
            func = func_type(vt[2])
            func(obj)


__all__ = ['CfbWriter']
