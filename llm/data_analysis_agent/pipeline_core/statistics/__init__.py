"""
Portable statistical analysis, forecasting, and diagnostic engines.
Air-gapped runtime compliant with zero plotting binary dependencies.
"""

from pipeline_core.statistics.forecast import forecast

try:
    from pipeline_core.statistics.anomaly_spotlight import AnomalySpotlight
except ImportError:
    pass

try:
    from pipeline_core.statistics.blame_bridge import BlameBridge
except ImportError:
    pass

try:
    from pipeline_core.statistics.domino_timeline import DominoTimeline
except ImportError:
    pass

__all__ = [
    "forecast",
    "AnomalySpotlight",
    "BlameBridge",
    "DominoTimeline",
]
