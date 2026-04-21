class LibPkgWriter:
    @staticmethod
    def write(filename: str, schlib_name: str, pcblib_name: str):
        content = (
            '[Design]\r\n'
            'Version=1.0\r\n'
            'HierarchyMode=0\r\n'
            'ChannelRoomNamingStyle=0\r\n'
            '\r\n'
            '[Document1]\r\n'
            f'DocumentPath={schlib_name}\r\n'
            'AnnotationEnabled=1\r\n'
            'AnnotateStartValue=1\r\n'
            'AnnotationIndexControlEnabled=0\r\n'
            'AnnotateSuffix=\r\n'
            'AnnotateScope=All\r\n'
            'AnnotateOrder=-1\r\n'
            '\r\n'
            '[Document2]\r\n'
            f'DocumentPath={pcblib_name}\r\n'
            'AnnotationEnabled=1\r\n'
            'AnnotateStartValue=1\r\n'
            'AnnotationIndexControlEnabled=0\r\n'
            'AnnotateSuffix=\r\n'
            'AnnotateScope=All\r\n'
            'AnnotateOrder=-1\r\n'
        )
        with open(filename, 'wb') as file:
            file.write(content.encode('ascii'))


__all__ = ['LibPkgWriter']
