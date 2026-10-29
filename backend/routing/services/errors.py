class UpstreamError(Exception):
    """A provider we depend on failed or answered with something unusable."""

    def __init__(self, code: str, message: str, retry_after_s: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_s = retry_after_s


class NotFound(Exception):
    """Input was well-formed but resolved to nothing (e.g. an address no geocoder knows)."""

    def __init__(self, code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
