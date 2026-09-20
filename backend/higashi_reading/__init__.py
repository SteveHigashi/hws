"""higashi_reading — the walk reading, shared by the free product and Higashi Live.

Pure: pydantic models and functions only. Lives under backend/ because the free
product ships everywhere (server, sidecar); Live receives a copy of this directory
from its deploy script.
"""
from .deterministic import (  # noqa: F401
    AI_SEARCH_CAVEAT,
    KNOWN_ROBOTS_IGNORERS,
    SEARCH_CRAWLERS,
    changes_between,
    deterministic_reading,
    headline,
    no_comparison_notes,
    robots_paragraph,
    size_bucket,
)
from .prompt import SYSTEM_PROMPT, constrain_model_reading, parse_model_json  # noqa: F401
from .schemas import Crawler, GeoResult, ReadingBody, ReportIn, StrictModel, Walk  # noqa: F401
