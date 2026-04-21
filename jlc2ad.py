#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility entrypoint for jlc2ad CLI and helper imports."""

import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        from jlc2ad_core.gui import main as gui_main
        gui_main()
    else:
        from jlc2ad_core.cli import main as cli_main
        cli_main()


from jlc2ad_core import BuildResult, build_libraries, normalize_output_base
from jlc2ad_core.easyeda_api import EasyEDAClient
from jlc2ad_core.footprint_parser import FootprintParser
from jlc2ad_core.pcb_writer import PcbLibWriter, RecordPacker
from jlc2ad_core.sch_writer import SchLibWriter
from jlc2ad_core.schematic_parser import SchematicParser
from jlc2ad_core.writers import (
    CfbWriter,
    LibPkgWriter,
    _safe_storage_name,
    _write_cstring_param_block,
    _write_string_block,
)

__all__ = [
    'main',
    'BuildResult',
    'build_libraries',
    'normalize_output_base',
    'EasyEDAClient',
    'FootprintParser',
    'SchematicParser',
    'RecordPacker',
    'CfbWriter',
    'PcbLibWriter',
    'SchLibWriter',
    'LibPkgWriter',
    '_write_string_block',
    '_write_cstring_param_block',
    '_safe_storage_name',
]


if __name__ == '__main__':
    main()
