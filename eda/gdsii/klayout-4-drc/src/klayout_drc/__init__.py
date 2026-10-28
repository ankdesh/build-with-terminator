"""KLayout DRC Analysis and Repair Package.

Exposes the runner, parser, reporter, and fixer classes for programmatic
DRC workflows with KLayout and DeepSeek Harness integration.
"""

from .config import (
    DEFAULT_GDS_PATH,
    DEFAULT_DRC_SCRIPT_PATH,
    DEFAULT_REPORT_DB_PATH,
    DEFAULT_TEXT_REPORT_PATH,
    DRCJobConfig,
    DRCError,
    DRCConfigurationError,
    DRCExecutionError,
    DRCParserError,
)
# Setup and archive commands must start before third-party packages are installed.
# Keep the public API, but load geometry modules only when callers use them.
from importlib import import_module

_LAZY = {
    'runner': ('DRCRunner',),
    'parser': ('DRCParser', 'DRCReportData', 'RuleCategory', 'ViolationItem', 'ViolationGeometry'),
    'reporter': ('DRCReporter',),
    'fixer': ('DRCFixer',),
    'drc_context': ('DRCContextProcessor', 'ExtractedRuleInfo'),
    'gds_context': ('GDSContextProcessor', 'ViolationNeighborhoodWindow', 'PolygonGeometry'),
    'knowledge_loader': ('KnowledgeLoader', 'KnowledgeDocument'),
}


def __getattr__(name):
    for module, names in _LAZY.items():
        if name in names:
            value = getattr(import_module(f'.{module}', __name__), name)
            globals()[name] = value
            return value
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


__all__ = [
    "DEFAULT_GDS_PATH",
    "DEFAULT_DRC_SCRIPT_PATH",
    "DEFAULT_REPORT_DB_PATH",
    "DEFAULT_TEXT_REPORT_PATH",
    "DRCJobConfig",
    "DRCError",
    "DRCConfigurationError",
    "DRCExecutionError",
    "DRCParserError",
    "DRCRunner",
    "DRCParser",
    "DRCReportData",
    "RuleCategory",
    "ViolationItem",
    "ViolationGeometry",
    "DRCReporter",
    "DRCFixer",
    "DRCContextProcessor",
    "ExtractedRuleInfo",
    "GDSContextProcessor",
    "ViolationNeighborhoodWindow",
    "PolygonGeometry",
    "KnowledgeLoader",
    "KnowledgeDocument",
]
