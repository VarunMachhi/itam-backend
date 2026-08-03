"""
Tiny semantic-version-ish comparison helper.

Deliberately dependency-free (no `packaging` package required) since this
only ever needs to compare simple "1.4.2" / "v1.4.2" style strings that the
admin types into the AppRelease form -- not full PEP 440 version specs.
"""
import re

_VERSION_RE = re.compile(r'\d+')


def parse_version(version_string):
    """'v1.4.2' -> (1, 4, 2). Non-numeric junk is ignored rather than
    raising, so a malformed version string sorts as (0,) instead of
    crashing the admin page or the public API."""
    return tuple(int(n) for n in _VERSION_RE.findall(version_string or '')) or (0,)


def is_newer(candidate, baseline):
    """True if `candidate` version string is newer than `baseline`."""
    return parse_version(candidate) > parse_version(baseline)
