"""Shared input-path plumbing for legacy report builders.

The front door sets these variables for a disposable report workspace. Historical
records stay byte-for-byte unchanged. Direct legacy invocations still work.
"""
import os
import json
from pathlib import Path

ROOT = Path(os.environ.get('DRC_REPORT_ROOT', Path(__file__).resolve().parents[3])).resolve()
FONTS = Path(os.environ.get('DRC_REPORT_FONTS', '/usr/share/fonts/truetype/dejavu'))
ORIGINAL_ROOT = Path(os.environ.get('DRC_REPORT_ORIGINAL_ROOT', ROOT))


def resolve_record(value):
    path = Path(value)
    if path.is_absolute():
        for alias in sorted(json.loads(os.environ.get('DRC_REPORT_PATH_MAP', '[]')), key=lambda a: len(a['original']), reverse=True):
            if path.is_relative_to(alias['original']):
                return ROOT/alias['prefix']/path.relative_to(alias['original'])
        try: return ROOT/path.relative_to(ORIGINAL_ROOT)
        except ValueError:
            if path.is_relative_to(ROOT): return path
            raise ValueError(f'Record path is outside the source project: {path}')
    if '..' in path.parts: raise ValueError(f'Unsafe report input: {value}')
    return ROOT/path
