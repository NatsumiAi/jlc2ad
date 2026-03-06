# AGENTS.md - jlc2ad Development Guide

## Project Overview

`jlc2ad` is a Python tool that fetches component footprints and schematic symbols from EasyEDA/LCSC and converts them to Altium Designer format (PcbLib + SchLib + LibPkg).

- **Main file**: `jlc2ad.py` (1362 lines)
- **Python version**: 3.12+
- **Dependencies**: `requests`, `olefile`

---

## Build / Run Commands

### Running the tool

```bash
# Basic usage - fetch single component
python jlc2ad.py C15850 -o my_lib

# Multiple components
python jlc2ad.py C15850 C25804 C7171 -o my_lib

# Append to existing library
python jlc2ad.py C100023 -o my_lib
```

### Running tests

This project does **not** have a formal test framework. Test files are generated manually:

```bash
# Generate test PcbLib files (requires RC.PcbLib reference file)
python gen_tests.py
```

To add tests, consider using `pytest`:

```bash
# Install pytest
pip install pytest

# Run all tests
pytest

# Run single test file
pytest test_file.py

# Run single test function
pytest test_file.py::test_function_name

# Run with verbose output
pytest -v
```

### Code quality tools

```bash
# Install linting tools
pip install ruff black mypy

# Run ruff (linting)
ruff check .

# Run ruff with auto-fix
ruff check --fix .

# Run black (formatting)
black .

# Run mypy (type checking)
mypy .
```

---

## Code Style Guidelines

### General Principles

- Write clear, readable code with descriptive names
- Keep functions focused and small (under 50 lines when possible)
- Add docstrings to public functions and classes
- Handle errors gracefully with informative messages

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Modules | snake_case | `jlc2ad.py` |
| Classes | PascalCase | `EasyEDAClient`, `FootprintParser` |
| Functions | snake_case | `def fetch()`, `def parse()` |
| Variables | snake_case | `lcsc_id`, `footprints` |
| Constants | UPPER_CASE | `UNIT_SCALE`, `PAD_SHAPE_ROUND` |
| Dataclass fields | snake_case | `x: int`, `hole_size: int` |

### Type Hints

- Use type hints for all function parameters and return types
- Use `Optional[X]` instead of `X | None`
- Use `List[X]`, `Dict[K, V]` from `typing` (or `list[K]` in Python 3.9+)

```python
# Good
def parse(self, component_data: dict) -> Optional[Footprint]:
    ...

def pack_pad(self, pad: Pad) -> bytes:
    ...

# Avoid
def parse(self, data):  # Missing types
```

### Imports

Organize imports in the following order (PEP 8):

1. Standard library
2. Third-party libraries
3. Local application imports

```python
import struct
import math
import re
import sys
import os
import argparse
import zlib
import base64
from dataclasses import dataclass, field
from typing import List, Optional

import requests
```

### Dataclasses

Use `@dataclass` for simple data structures:

```python
@dataclass
class Pad:
    x: int = 0
    y: int = 0
    size_x: int = 0
    size_y: int = 0
    hole_size: int = 0
    shape: int = PAD_SHAPE_RECT
    rotation: float = 0.0
    layer: int = 1
    name: str = "1"
    plated: bool = True
```

### Error Handling

- Use specific exception types when possible
- Provide informative error messages
- Catch exceptions at the appropriate level

```python
# Good
if not data.get('success'):
    raise ValueError(f"API error: {data}")

if not result:
    raise ValueError(f"Component {lcsc_id} not found")

# Good - catching and logging
except Exception as e:
    print(f"  Warning: parse {shape_type} failed: {e}")
    continue
```

### Constants

Group constants at the module level with clear comments:

```python
# ============================================================
# Constants
# ============================================================

LAYER_MAP = {
    1:  1,    # TopLayer
    2:  32,   # BottomLayer
    ...
}
```

### Docstrings

Use docstrings for all public classes and functions:

```python
class EasyEDAClient:
    """EasyEDA API client for fetching component data."""

    def fetch(self, lcsc_id: str) -> dict:
        """Fetch component data from EasyEDA API.
        
        Args:
            lcsc_id: LCSC part number (e.g., 'C15850')
            
        Returns:
            Dictionary containing component data
            
        Raises:
            ValueError: If component not found or API error
        """
```

### File Organization

Follow this structure in source files:

1. Shebang and encoding (if needed)
2. Module docstring
3. Imports
4. Constants
5. Data classes (dataclasses)
6. Helper functions
7. Main classes
8. Main execution block

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module description...
"""

import ...

# ============================================================
# Constants
# ============================================================

# ============================================================
# Data Classes
# ============================================================

# ============================================================
# Helper Functions
# ============================================================

# ============================================================
# Main Classes
# ============================================================

# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    main()
```

### Windows-Specific Code

This project uses Windows-specific APIs (`ctypes.windll`). When modifying:

- Keep Windows-specific code isolated in dedicated methods/classes
- Add platform checks where appropriate
- Test on Windows environment

---

## Common Tasks

### Adding a new component type

1. Add designator mapping in `EasyEDAClient._guess_designator()`
2. Update parsing logic in `FootprintParser` or `SchematicParser`
3. Test with actual LCSC component

### Modifying binary format

The binary packing logic is in `RecordPacker` class. Changes here affect:
- `PcbLibWriter` - PCB library output
- `SchLibWriter` - Schematic library output

---

## File Structure

```
jlc2ad.py          - Main application
gen_tests.py       - Test file generator
test_*.PcbLib      - Generated test libraries
test_min.PcbLib    - Minimal test component
my_lib.*           - User-generated output
```
