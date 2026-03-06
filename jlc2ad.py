#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility entrypoint for jlc2ad CLI and helper imports."""

from jlc2ad_core.cli import main
from jlc2ad_core.parsers import EasyEDAClient, FootprintParser, SchematicParser
from jlc2ad_core.writers import (
    CfbWriter,
    LibPkgWriter,
    PcbLibWriter,
    RecordPacker,
    SchLibWriter,
    _safe_storage_name,
    _write_cstring_param_block,
    _write_string_block,
)

__all__ = [
    'main',
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
