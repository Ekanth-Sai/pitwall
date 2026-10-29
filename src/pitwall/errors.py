"""Exception hierarchy for pitwall.
Catch PitwallError to handle anything this package raises on purpose.
Programmer mistakes (bad arguments) raise ValueError instead"""


class PitwallError(Exception):
    """Base class for all pitwall errors"""


class SourceError(PitwallError):
    """An upstream data source failed: network, auth, or server error"""


class InvalidQueryError(PitwallError):
    """A query was rejected before being sent (unknown endpoint or field)"""


class SchemaError(PitwallError):
    """Data from a source did not have the expected shape"""
