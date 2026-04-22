"""Schema version and resource limits for agent-harness.

When making BREAKING changes to the log format, bump SCHEMA_MAJOR.
Logs written under a different major version will be rejected by the parser.
"""

SCHEMA_VERSION = "1.0"
SCHEMA_MAJOR = 1

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB cap per log file
MAX_FIELD_CHARS = 100_000          # cap per parsed field to prevent silly inputs


class HarnessVersionError(Exception):
    """Raised when a log file's schema version is incompatible."""


class HarnessSizeError(Exception):
    """Raised when a log file exceeds MAX_FILE_BYTES."""


def check_version(version_str: str) -> None:
    """Raise HarnessVersionError if version_str's major doesn't match SCHEMA_MAJOR."""
    if not version_str:
        return  # absent = treat as current
    try:
        major = int(str(version_str).split(".")[0])
    except (ValueError, AttributeError):
        raise HarnessVersionError(
            f"Invalid harness_version: {version_str!r}. Expected 'major.minor' (e.g. '1.0')."
        )
    if major != SCHEMA_MAJOR:
        raise HarnessVersionError(
            f"Log written for harness schema v{major}.x but this CLI is v{SCHEMA_MAJOR}.x. "
            f"Upgrade or downgrade agent-harness to match, or migrate the logs."
        )
