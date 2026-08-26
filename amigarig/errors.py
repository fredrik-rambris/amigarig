"""Common base for "this is a config/environment problem, not an amigarig
bug" errors. cli.py catches this to print a one-line message instead of a
full traceback; anything that's genuinely a bug should keep raising a
plain exception so it still surfaces with a traceback."""
from __future__ import annotations


class AmigarigError(Exception):
    pass
