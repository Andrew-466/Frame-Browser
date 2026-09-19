"""PyInstaller entry point for Frame.

`frame/__main__.py` uses relative imports (`.core`, `.main_window`, etc.)
which fail when PyInstaller runs it as a standalone script. This file
imports the package by absolute path so Python loads `frame` as a proper
package first.
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    from frame.__main__ import main
    sys.exit(main())