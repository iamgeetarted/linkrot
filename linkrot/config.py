"""Load configuration from .linkrot.toml or ~/.linkrot.toml."""

import tomllib
from pathlib import Path
from typing import Any


_CONFIG_FILENAME = ".linkrot.toml"

_VALID_KEYS = {"timeout", "workers", "ignore", "format", "show_ok", "no_external"}


def _load_raw(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"Invalid TOML in {path}: {e}") from e


def load_config() -> dict[str, Any]:
    """Return merged config, local .linkrot.toml taking precedence over ~/.linkrot.toml."""
    home_cfg = _load_raw(Path.home() / _CONFIG_FILENAME)
    local_cfg = _load_raw(Path.cwd() / _CONFIG_FILENAME)

    merged: dict[str, Any] = {**home_cfg, **local_cfg}

    unknown = set(merged) - _VALID_KEYS
    if unknown:
        raise ValueError(f"Unknown config key(s): {', '.join(sorted(unknown))}")

    if "timeout" in merged and not isinstance(merged["timeout"], (int, float)):
        raise ValueError("Config 'timeout' must be a number")
    if "workers" in merged and not isinstance(merged["workers"], int):
        raise ValueError("Config 'workers' must be an integer")
    if "ignore" in merged:
        if not isinstance(merged["ignore"], list) or not all(
            isinstance(s, str) for s in merged["ignore"]
        ):
            raise ValueError("Config 'ignore' must be a list of strings")
    if "format" in merged and merged["format"] not in {"table", "json", "csv", "markdown", "github", "sarif"}:
        raise ValueError("Config 'format' must be one of: table, json, csv, markdown, github, sarif")
    if "show_ok" in merged and not isinstance(merged["show_ok"], bool):
        raise ValueError("Config 'show_ok' must be a boolean")
    if "no_external" in merged and not isinstance(merged["no_external"], bool):
        raise ValueError("Config 'no_external' must be a boolean")

    return merged
