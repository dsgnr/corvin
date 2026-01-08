"""
Generic helpers
"""


def _parse_percent(value: str) -> float:
    try:
        return float(value.strip().rstrip("%"))
    except (ValueError, AttributeError):
        return 0.0
