class UpstreamError(Exception):
    """A provider we depend on failed or answered with something unusable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class NotFound(Exception):
    """Input was well-formed but resolved to nothing (e.g. an address no geocoder knows)."""

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
