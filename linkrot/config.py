"""Load configuration from .linkrot.toml or ~/.linkrot.toml."""

import tomllib
from pathlib import Path
from typing import Any


_CONFIG_FILENAME = ".linkrot.toml"

_VALID_KEYS = {
    # Original keys
    "timeout", "workers", "ignore", "format", "show_ok", "no_external",
    # Added in v1.3
    "cache_ttl", "no_cache", "suggest", "verbose",
    # Added in v1.5
    "retries", "retry_backoff", "show_redirects", "watch",
    # Added in v1.6
    "sitemap",
    # Added in v1.7
    "domain_summary", "log_file",
    # Added in v1.8
    "notify_webhook", "notify_broken_only",
}

_VALID_FORMATS = {"table", "json", "csv", "markdown", "github", "sarif", "html"}


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

    # Type validation
    _float_keys = {"timeout", "cache_ttl", "retry_backoff"}
    _int_keys = {"workers", "retries", "watch"}
    _bool_keys = {
        "show_ok", "no_external", "no_cache", "suggest", "verbose",
        "show_redirects", "sitemap", "domain_summary", "notify_broken_only",
    }
    _str_keys = {"format", "log_file", "notify_webhook"}

    for k in _float_keys:
        if k in merged and not isinstance(merged[k], (int, float)):
            raise ValueError(f"Config '{k}' must be a number")

    for k in _int_keys:
        if k in merged and not isinstance(merged[k], int):
            raise ValueError(f"Config '{k}' must be an integer")

    for k in _bool_keys:
        if k in merged and not isinstance(merged[k], bool):
            raise ValueError(f"Config '{k}' must be a boolean")

    for k in _str_keys:
        if k in merged and not isinstance(merged[k], str):
            raise ValueError(f"Config '{k}' must be a string")

    if "ignore" in merged:
        if not isinstance(merged["ignore"], list) or not all(
            isinstance(s, str) for s in merged["ignore"]
        ):
            raise ValueError("Config 'ignore' must be a list of strings")

    if "format" in merged and merged["format"] not in _VALID_FORMATS:
        raise ValueError(
            f"Config 'format' must be one of: {', '.join(sorted(_VALID_FORMATS))}"
        )

    return merged
