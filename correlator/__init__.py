"""
Correlation engine for matching fragments across compilation stages.
"""

from .loc_index import SourceRange, LocationIndex
from .matcher import FuzzyMatcher
from .graph import TraceGraph

__all__ = ['SourceRange', 'LocationIndex', 'FuzzyMatcher', 'TraceGraph']
