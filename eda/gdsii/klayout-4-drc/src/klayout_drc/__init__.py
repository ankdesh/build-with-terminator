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
from .runner import DRCRunner
from .parser import DRCParser, DRCReportData, RuleCategory, ViolationItem, ViolationGeometry
from .reporter import DRCReporter
from .fixer import DRCFixer
from .drc_context import DRCContextProcessor, ExtractedRuleInfo
from .gds_context import GDSContextProcessor, ViolationNeighborhoodWindow, PolygonGeometry
from .knowledge_loader import KnowledgeLoader, KnowledgeDocument

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
