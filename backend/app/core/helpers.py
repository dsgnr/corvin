"""Generic helpers"""

import tomllib
from pathlib import Path

_pyproject_data: dict | None = None


def _get_pyproject() -> dict:
    """Load and cache pyproject.toml data."""
    global _pyproject_data
    if _pyproject_data is None:
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            _pyproject_data = tomllib.load(f)
            print(_pyproject_data)
    return _pyproject_data


def _get_pyproject_attr(key: str, default: str = "unknown") -> str:
    """Get an attribute from pyproject.toml [tool.poetry] section."""
    try:
        return _get_pyproject()["project"].get(key, default)
    except Exception:
        return default
